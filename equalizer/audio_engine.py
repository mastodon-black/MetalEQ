"""PulseAudio/PipeWire + GStreamer backend for MetalEQ.

Signal path:
    any app -> [null sink: metal_eq_sink] -> (monitor) -> GStreamer
    pipeline (equalizer-nbands + preamp) -> real output sink

Apps are routed into the equalizer by pointing the PulseAudio default sink
at our null sink (and optionally moving already-running streams onto it).
"""
import json
import subprocess
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

Gst.init(None)

NULL_SINK_NAME = "metal_eq_sink"
NULL_SINK_DESC = "Equalizer"

# Tag applied to our own output stream's PulseAudio/PipeWire properties so we
# can reliably find and re-pin it to the chosen real device. This matters
# because pulsesink's "device" property occasionally loses a race against our
# own default-sink switch and binds to the (wrong, just-changed) default sink
# instead -- silently looping our output back into our own input.
OUTPUT_STREAM_TAG = "MetalEQOutput"

# Center frequency (Hz) of each band. Using equalizer-nbands (not the fixed
# equalizer-10bands) so these -- and each band's Q/bandwidth -- are real,
# adjustable parametric-EQ properties, not a hardcoded filter bank.
BAND_FREQS = [29, 59, 119, 237, 474, 947, 1889, 3770, 7523, 15011]
# Friendlier labels for the UI (close to the classic 10-band EQ scale)
BAND_LABELS = ["32", "64", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]

BAND_MIN_DB = -24.0
BAND_MAX_DB = 12.0

# Q (freq / bandwidth_hz): higher = narrower/more surgical, lower = wider/
# more musical. Default of ~1.41 approximates the ~1-octave-wide bands a
# fixed 10-band graphic EQ uses, so the starting sound is unchanged.
BAND_Q_MIN = 0.3
BAND_Q_MAX = 5.0
BAND_Q_DEFAULT = 1.41

PREAMP_MIN_DB = -20.0
PREAMP_MAX_DB = 20.0

# Max extra gain (dB) added to the low bands (32/64/125 Hz) when Bass Boost is
# at 100%, layered on top of whatever the sliders/preset are set to. Scaled
# linearly by the Bass Boost level (0-100).
BASS_BOOST_OFFSETS = [6.0, 4.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

# audiodynamic compressor settings at 100% Vocal Normalize intensity
# (soft-knee compression that evens out loud/quiet passages). Scaled
# linearly by the Vocal Normalize level (0-100); 0 is a true bypass.
#
# The compressor alone only pulls loud peaks down -- it has no makeup-gain
# property, so anything below the threshold (the quiet parts we actually
# want louder) passes through completely unchanged. That made the effect
# imperceptible as "normalization": things only ever got quieter, never
# more even. VOCAL_NORM_MAKEUP_GAIN_MAX compensates with a post-compressor
# gain stage so quiet passages are actually boosted, measured empirically:
# a full-scale tone through the max compressor settings comes out at ~76%
# of its original peak, so ~1.25x brings it back toward (not quite to,
# for headroom) its original level -- and lifts everything quieter with it.
VOCAL_NORM_RATIO_MAX = 0.35
VOCAL_NORM_THRESHOLD_MAX = 0.25
VOCAL_NORM_MAKEUP_GAIN_MAX = 1.25


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _pactl(*args):
    return _run(["pactl", *args])


class AudioEngineError(RuntimeError):
    pass


class AudioEngine:
    def __init__(self):
        self.pipeline = None
        self.eq = None
        self.preamp = None
        self.normalizer = None
        self.normalizer_gain = None
        self._module_id = None
        self._previous_default_sink = None
        self._moved_stream_indices = []
        self.running = False

    # ---------------------------------------------------------------- devices
    @staticmethod
    def list_output_sinks():
        """Return [(name, description)] for real (non-virtual) output sinks."""
        result = _pactl("-f", "json", "list", "sinks")
        if result.returncode != 0:
            return []
        try:
            sinks = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        out = []
        for sink in sinks:
            name = sink.get("name", "")
            if name == NULL_SINK_NAME:
                continue
            out.append((name, sink.get("description", name)))
        return out

    @staticmethod
    def get_system_default_sink():
        result = _pactl("get-default-sink")
        name = result.stdout.strip()
        if result.returncode != 0 or not name or name == NULL_SINK_NAME:
            return None
        return name

    @staticmethod
    def recover_stale_state():
        """Clean up after a previous run that didn't exit cleanly: remove
        any orphaned virtual sink, and if the system default sink is still
        pointed at it, fall back to a real output device."""
        AudioEngine._cleanup_stale_null_sink()
        result = _pactl("get-default-sink")
        current = result.stdout.strip()
        if result.returncode == 0 and (not current or current == NULL_SINK_NAME):
            sinks = AudioEngine.list_output_sinks()
            if sinks:
                _pactl("set-default-sink", sinks[0][0])

    @staticmethod
    def _cleanup_stale_null_sink():
        """Unload any leftover null sink module from a previous crashed run."""
        result = _pactl("list", "modules", "short")
        if result.returncode != 0:
            return
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            index, name, argument = parts[0], parts[1], parts[2]
            if name == "module-null-sink" and NULL_SINK_NAME in argument:
                _pactl("unload-module", index)

    # ---------------------------------------------------------------- engine
    def start(self, output_sink_name, route_existing_streams=True):
        if self.running:
            return

        self._cleanup_stale_null_sink()

        result = _pactl(
            "load-module",
            "module-null-sink",
            f"sink_name={NULL_SINK_NAME}",
            f"sink_properties=device.description={NULL_SINK_DESC}",
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise AudioEngineError(
                f"Failed to create virtual sink: {result.stderr.strip()}"
            )
        self._module_id = result.stdout.strip()

        pipeline_desc = (
            f'pulsesrc device="{NULL_SINK_NAME}.monitor" '
            "! audioconvert ! audioresample "
            "! equalizer-nbands name=eq num-bands=10 "
            "! audiodynamic name=normalizer ratio=1.0 threshold=0.0 "
            "! volume name=normalizer_gain volume=1.0 "
            "! volume name=preamp "
            "! audioconvert "
            f'! pulsesink name=outsink device="{output_sink_name}"'
        )
        try:
            self.pipeline = Gst.parse_launch(pipeline_desc)
        except Exception as exc:
            self._teardown_null_sink()
            raise AudioEngineError(f"Failed to build pipeline: {exc}") from exc

        self.eq = self.pipeline.get_by_name("eq")
        self.preamp = self.pipeline.get_by_name("preamp")
        self.normalizer = self.pipeline.get_by_name("normalizer")
        self.normalizer_gain = self.pipeline.get_by_name("normalizer_gain")

        for i, freq in enumerate(BAND_FREQS):
            band = self.eq.get_child_by_index(i)
            band.set_property("freq", float(freq))
            band.set_property("bandwidth", float(freq) / BAND_Q_DEFAULT)

        outsink = self.pipeline.get_by_name("outsink")
        outsink.set_property(
            "stream-properties",
            Gst.Structure.new_from_string(
                f"props,application.name={OUTPUT_STREAM_TAG}"
            ),
        )

        state_ret = self.pipeline.set_state(Gst.State.PLAYING)
        if state_ret == Gst.StateChangeReturn.FAILURE:
            self.pipeline.set_state(Gst.State.NULL)
            self._teardown_null_sink()
            self.pipeline = None
            self.eq = None
            self.preamp = None
            self.normalizer = None
            self.normalizer_gain = None
            raise AudioEngineError("GStreamer pipeline failed to start.")

        self.running = True

        if route_existing_streams:
            self._route_default_and_streams()

        self._pin_own_stream(output_sink_name)

    def _pin_own_stream(self, output_sink_name):
        """Find our own tagged output stream and force it onto the real
        device, correcting it if it bound to the wrong (default) sink."""
        for _attempt in range(10):
            result = _pactl("-f", "json", "list", "sink-inputs")
            if result.returncode == 0:
                try:
                    items = json.loads(result.stdout)
                except json.JSONDecodeError:
                    items = []
                for item in items:
                    props = item.get("properties", {})
                    if props.get("application.name") == OUTPUT_STREAM_TAG:
                        _pactl(
                            "move-sink-input", str(item["index"]), output_sink_name
                        )
                        return
            time.sleep(0.1)

    def _route_default_and_streams(self):
        current_default = _pactl("get-default-sink").stdout.strip()
        if current_default and current_default != NULL_SINK_NAME:
            self._previous_default_sink = current_default
        _pactl("set-default-sink", NULL_SINK_NAME)

        result = _pactl("-f", "json", "list", "sink-inputs")
        self._moved_stream_indices = []
        if result.returncode == 0:
            try:
                inputs = json.loads(result.stdout)
            except json.JSONDecodeError:
                inputs = []
            for item in inputs:
                index = item.get("index")
                if index is None:
                    continue
                if item.get("properties", {}).get("application.name") == OUTPUT_STREAM_TAG:
                    continue
                move = _pactl("move-sink-input", str(index), NULL_SINK_NAME)
                if move.returncode == 0:
                    self._moved_stream_indices.append(index)

    def stop(self):
        if not self.running:
            return

        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.NULL)

        if self._previous_default_sink:
            _pactl("set-default-sink", self._previous_default_sink)
            result = _pactl("-f", "json", "list", "sink-inputs")
            if result.returncode == 0:
                try:
                    inputs = json.loads(result.stdout)
                except json.JSONDecodeError:
                    inputs = []
                for item in inputs:
                    if item.get("index") in self._moved_stream_indices:
                        _pactl(
                            "move-sink-input",
                            str(item["index"]),
                            self._previous_default_sink,
                        )

        self._teardown_null_sink()

        self.pipeline = None
        self.eq = None
        self.preamp = None
        self.normalizer = None
        self.normalizer_gain = None
        self._previous_default_sink = None
        self._moved_stream_indices = []
        self.running = False

    def _teardown_null_sink(self):
        if self._module_id:
            _pactl("unload-module", self._module_id)
            self._module_id = None

    # ----------------------------------------------------------------- bands
    def set_band(self, index, db_value):
        if self.eq is not None:
            self.eq.get_child_by_index(index).set_property("gain", float(db_value))

    def set_band_q(self, index, q_value):
        if self.eq is not None:
            q_value = max(BAND_Q_MIN, min(BAND_Q_MAX, float(q_value)))
            bandwidth = BAND_FREQS[index] / q_value
            self.eq.get_child_by_index(index).set_property("bandwidth", bandwidth)

    def set_preamp_db(self, db_value):
        if self.preamp is not None:
            linear = 10 ** (float(db_value) / 20.0)
            self.preamp.set_property("volume", linear)

    def set_vocal_normalization(self, level):
        """level: 0-100. 0 is a true bypass; 100 is full compression with
        makeup gain, so quiet passages are actually boosted rather than
        just pulling loud peaks down."""
        if self.normalizer is None:
            return
        frac = max(0.0, min(1.0, float(level) / 100.0))
        if frac <= 0:
            self.normalizer.set_property("ratio", 1.0)
            self.normalizer.set_property("threshold", 0.0)
            if self.normalizer_gain is not None:
                self.normalizer_gain.set_property("volume", 1.0)
            return
        self.normalizer.set_property("mode", 0)  # compressor
        self.normalizer.set_property("characteristics", 1)  # soft-knee
        ratio = 1.0 - frac * (1.0 - VOCAL_NORM_RATIO_MAX)
        threshold = frac * VOCAL_NORM_THRESHOLD_MAX
        self.normalizer.set_property("ratio", ratio)
        self.normalizer.set_property("threshold", threshold)
        if self.normalizer_gain is not None:
            makeup = 1.0 + frac * (VOCAL_NORM_MAKEUP_GAIN_MAX - 1.0)
            self.normalizer_gain.set_property("volume", makeup)

    def poll_errors(self):
        """Return an error string from the GStreamer bus, or None."""
        if self.pipeline is None:
            return None
        bus = self.pipeline.get_bus()
        msg = bus.pop_filtered(Gst.MessageType.ERROR)
        if msg is None:
            return None
        err, debug = msg.parse_error()
        return str(err)
