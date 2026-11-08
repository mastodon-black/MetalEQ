"""Dark theme palette + stylesheet for the equalizer GUI."""
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import Qt

BG = "#1e1f24"
BG_ALT = "#26282f"
PANEL = "#2c2e36"
BORDER = "#3a3d47"
ACCENT = "#2ecc71"
ACCENT_DIM = "#1f7a4d"
ACCENT_LIGHT = "#58e090"
TEXT = "#e6e6eb"
TEXT_DIM = "#9a9ca5"
DANGER = "#ff5c5c"
GOOD = "#4cd787"
HEADER_FONT = "Cinzel"

STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Space Grotesk", "Ubuntu Sans", "Noto Sans", sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {BG};
}}

QLabel, QSlider {{
    background-color: transparent;
}}

QLabel#bandFreq {{
    color: {TEXT_DIM};
    font-size: 11px;
}}

QLabel#bandGain {{
    color: {ACCENT};
    font-size: 11px;
    font-weight: 600;
}}

QLabel#status {{
    color: {TEXT_DIM};
    font-size: 12px;
}}

QFrame#freqRow {{
    background-color: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 3px;
}}

QLabel#sectionHeader {{
    font-family: "{HEADER_FONT}", "Ubuntu Sans", sans-serif;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 1px;
    color: {TEXT};
}}

QFrame#panel {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}

QComboBox, QPushButton {{
    background-color: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 6px 10px;
    color: {TEXT};
}}

QComboBox:hover, QPushButton:hover {{
    border: 1px solid {ACCENT_DIM};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_ALT};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_DIM};
    color: {TEXT};
}}

QPushButton {{
    font-weight: 500;
}}

QPushButton:pressed {{
    background-color: {ACCENT_DIM};
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
}}

QPushButton#enableButton {{
    background-color: {DANGER};
    color: #1a0b0b;
    border: none;
    font-weight: 600;
    padding: 8px 10px;
}}

QPushButton#enableButton:hover {{
    background-color: #ff7a7a;
}}

QPushButton#enableButton:checked {{
    background-color: {GOOD};
    color: #10140f;
}}

QPushButton#enableButton:checked:hover {{
    background-color: #5fe69a;
}}

QSlider::groove:vertical {{
    background: {BG_ALT};
    border: none;
    width: 6px;
    border-radius: 2px;
}}

QSlider::handle:vertical {{
    background: {ACCENT};
    border: none;
    height: 14px;
    width: 14px;
    margin: 0 -5px;
    border-radius: 3px;
}}

QSlider::handle:vertical:hover {{
    background: {ACCENT_LIGHT};
}}

QSlider::sub-page:vertical {{
    background: {BG_ALT};
    border: none;
    border-radius: 2px;
}}

QSlider::add-page:vertical {{
    background: {ACCENT};
    border: none;
    border-radius: 2px;
}}

QSlider::groove:horizontal {{
    background: {BG_ALT};
    border: none;
    height: 6px;
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {ACCENT};
    border: none;
    height: 14px;
    width: 14px;
    margin: -5px 0;
    border-radius: 3px;
}}

QSlider::handle:horizontal:hover {{
    background: {ACCENT_LIGHT};
}}

QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border: none;
    border-radius: 2px;
}}

QSlider::add-page:horizontal {{
    background: {BG_ALT};
    border: none;
    border-radius: 2px;
}}

QSlider#qSlider::groove:horizontal {{
    background: {BG_ALT};
    border: none;
    height: 3px;
    border-radius: 1px;
}}

QSlider#qSlider::handle:horizontal {{
    background: {TEXT_DIM};
    border: none;
    height: 9px;
    width: 9px;
    margin: -3px 0;
    border-radius: 2px;
}}

QSlider#qSlider::handle:horizontal:hover {{
    background: {ACCENT};
}}

QSlider#qSlider::sub-page:horizontal,
QSlider#qSlider::add-page:horizontal {{
    background: {BG_ALT};
    border: none;
    border-radius: 1px;
}}

QScrollBar:vertical {{
    background: {BG};
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
}}

QToolTip {{
    background-color: {BG_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
"""


def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_ALT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_ALT))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(DANGER))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_DIM))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(TEXT_DIM))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
