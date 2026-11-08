"""App icon loaded from bundled files, not the system icon theme.

Relying on QIcon.fromTheme() meant the icon only rendered correctly if the
desktop's *active* icon theme happened to carry an "audio-equalizer" icon.
On this machine the active theme (Mint-Y-Sand) doesn't, so the window and
especially the system tray icon rendered as an unrecognizable blank/generic
glyph -- which is why the tray icon couldn't be found to quit from. Bundling
the PNGs sidesteps icon-theme resolution entirely.
"""
from pathlib import Path

from PyQt6.QtGui import QIcon

ICONS_DIR = Path(__file__).parent / "icons"
SIZES = (16, 24, 32, 48, 64, 96, 256)


def load_app_icon():
    icon = QIcon()
    for size in SIZES:
        path = ICONS_DIR / f"audio-equalizer-{size}.png"
        if path.exists():
            icon.addFile(str(path))
    return icon
