#!/usr/bin/env python3
import sys
from pathlib import Path

from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

from equalizer.gui import MainWindow
from equalizer.icon import load_app_icon
from equalizer.theme import apply_dark_theme

FONTS_DIR = Path(__file__).parent / "equalizer" / "fonts"


def main():
    app = QApplication(sys.argv)
    for font_file in ("Cinzel.ttf", "SpaceGrotesk.ttf"):
        font_path = FONTS_DIR / font_file
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
    apply_dark_theme(app)
    app.setQuitOnLastWindowClosed(False)
    icon = load_app_icon()
    app.setWindowIcon(icon)
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
