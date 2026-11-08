"""Persistence for user-defined EQ presets."""
import json
from pathlib import Path

from .audio_engine import BAND_Q_DEFAULT

CONFIG_DIR = Path.home() / ".config" / "linux-equalizer"
PRESETS_FILE = CONFIG_DIR / "presets.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

FLAT = [0.0] * 10
DEFAULT_PRESET_FALLBACK = "Metal"

# Hand-tuned presets that ship with the app (shown alongside Flat and any
# user presets, but not user-deletable). Bass Boost and Vocal Normalization
# are separate toggle switches in the GUI, not entries here.
# Band order: 32, 64, 125, 250, 500, 1k, 2k, 4k, 8k, 16k Hz
BUILTIN_EXTRA_PRESETS = {
    # Scooped-mids "V" curve: boosted lows/highs, gentle mid dip.
    "Metal": [5.0, 4.0, 1.5, -1.0, -2.5, -2.5, -1.0, 1.5, 4.0, 5.0],
    # Movies/TV: a little low-end punch, clear dialogue presence, airy top.
    "Media": [2.5, 2.0, 1.0, 0.5, 0.0, 1.5, 2.5, 3.0, 2.5, 1.5],
    # Gaming: tight sub-bass for impact, strong upper-mid/high boost so
    # footsteps and directional cues cut through, slight low-mid scoop
    # to keep things from getting muddy.
    "Gaming": [2.0, 1.0, 0.0, -1.0, -1.5, 1.0, 3.5, 4.5, 4.0, 2.5],
}


def load_custom_presets():
    """Return {name: {"bands": [...10 floats...], "q": [...10 floats...],
    "bass_boost": 0-100, "vocal_norm": 0-100, "preamp": dB float}}. Presets
    saved before a field existed are read back with it defaulting to its
    neutral value (0, or BAND_Q_DEFAULT for Q)."""
    if not PRESETS_FILE.exists():
        return {}
    try:
        with open(PRESETS_FILE, "r") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    result = {}
    for name, value in data.items():
        if isinstance(value, list) and len(value) == 10:
            result[name] = {
                "bands": value,
                "q": [BAND_Q_DEFAULT] * 10,
                "bass_boost": 0,
                "vocal_norm": 0,
                "preamp": 0.0,
            }
        elif isinstance(value, dict) and isinstance(value.get("bands"), list) and len(value["bands"]) == 10:
            q = value.get("q")
            if not (isinstance(q, list) and len(q) == 10):
                q = [BAND_Q_DEFAULT] * 10
            result[name] = {
                "bands": value["bands"],
                "q": [float(x) for x in q],
                "bass_boost": max(0, min(100, int(value.get("bass_boost", 0)))),
                "vocal_norm": max(0, min(100, int(value.get("vocal_norm", 0)))),
                "preamp": float(value.get("preamp", 0.0)),
            }
    return result


def save_custom_presets(presets):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(PRESETS_FILE, "w") as fh:
        json.dump(presets, fh, indent=2)


def add_preset(name, bands, bass_boost=0, vocal_norm=0, preamp=0.0, q=None):
    presets = load_custom_presets()
    presets[name] = {
        "bands": list(bands),
        "q": list(q) if q is not None else [BAND_Q_DEFAULT] * 10,
        "bass_boost": max(0, min(100, int(bass_boost))),
        "vocal_norm": max(0, min(100, int(vocal_norm))),
        "preamp": float(preamp),
    }
    save_custom_presets(presets)
    return presets


def delete_preset(name):
    presets = load_custom_presets()
    presets.pop(name, None)
    save_custom_presets(presets)
    return presets


def load_settings():
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, "r") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(settings):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as fh:
        json.dump(settings, fh, indent=2)


def get_default_preset():
    return load_settings().get("default_preset", DEFAULT_PRESET_FALLBACK)


def set_default_preset(name):
    settings = load_settings()
    settings["default_preset"] = name
    save_settings(settings)


def get_engine_enabled():
    return bool(load_settings().get("engine_enabled", False))


def set_engine_enabled(enabled):
    settings = load_settings()
    settings["engine_enabled"] = bool(enabled)
    save_settings(settings)
