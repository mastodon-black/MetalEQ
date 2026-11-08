# MetalEQ

**A free, system-wide audio equalizer for Linux, designed for metal.**

MetalEQ is a 10-band equalizer with a dark-mode PyQt6 GUI. It's free to use
and runs on Linux, on both PulseAudio and PipeWire (via pipewire-pulse).
Whatever you play, from any app, goes through it.

## Designed for metal

- Ships with a **Metal** preset, selected by default: a scooped-mids "V"
  curve with boosted lows and highs and a gentle mid dip.
- **Bass Boost** adds extra low-end on top of any preset or slider setting.
- **Vocal Normalize** evens out loud and quiet passages.
- **Media** and **Gaming** presets are included for everything else you
  listen to.

## How it works

- Creates a virtual PulseAudio sink (`metal_eq_sink`) and points the
  system default sink at it, moving already-playing streams onto it too.
- A GStreamer pipeline reads that sink's monitor, runs it through a 10-band
  parametric equalizer (`equalizer-nbands`) plus a preamp, and outputs to the real
  output device you choose.
- Stopping the equalizer restores your previous default sink and tears down
  the virtual sink.

## Install

```bash
./install.sh
```

On Debian/Ubuntu/Mint this installs the system packages below with `apt`
(asks for sudo only if something is missing), installs PyQt6, and then
checks that PyQt6, PyGObject and every GStreamer element the engine uses
are present. On other distros it prints what to install and still does the
PyQt6 step. Re-running it is safe.

Once everything checks out it also adds **MetalEQ to your app menu** and puts
an **icon on your desktop**. An existing `metal-eq.desktop` that launches a
different copy of MetalEQ is left alone, not overwritten.

On Windows, `install.bat` installs PyQt6 and creates a Desktop and Start menu
shortcut (`make_shortcuts.ps1`). The audio engine
(PulseAudio/PipeWire + GStreamer) is Linux-only.

## Dependencies

These are what `install.sh` sets up; to install them by hand instead:

- Python 3 with [PyGObject](https://pygobject.readthedocs.io/) (`gi`) and
  GStreamer 1.x with the `good` plugin set (for `equalizer-nbands`,
  `pulsesrc`/`pulsesink`). On Debian/Ubuntu/Mint:

  ```bash
  sudo apt install python3-gi gstreamer1.0-plugins-good gstreamer1.0-pulseaudio
  ```

- PyQt6 (installed to your user site-packages, no venv needed):

  ```bash
  pip install --user --break-system-packages -r requirements.txt
  ```

## Running

Linux:

```bash
./run.sh
```

Windows:

```bat
run.bat
```

or, on either platform:

```bash
python3 main.py
```

1. Pick your real output device from the dropdown.
2. Click **Start**. Audio from every app now flows through the equalizer.
3. Adjust the preamp and 10 band sliders, or pick a preset.
4. Click **Stop** to restore normal audio routing.

## Presets

Built-in presets: `Flat`, `Metal` (the default), `Media` and `Gaming`. Use
**Save As...** to store your own slider positions as a named preset (saved
to `~/.config/linux-equalizer/presets.json`).
