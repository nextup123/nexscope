"""
Theming: dark and light palettes built around the Nextup Robotics brand.

Brand colors sampled from the logo:
    brand blue   #0459F0
    deep navy    #02195C
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6 import QtGui, QtWidgets
from PyQt6.QtGui import QColor, QPalette

BRAND_BLUE = "#0459F0"
BRAND_NAVY = "#02195C"


@dataclass(frozen=True)
class Theme:
    name: str
    window: str
    base: str  # input/list backgrounds
    alt_base: str
    text: str
    dim_text: str
    button: str
    border: str
    plot_bg: str
    grid_alpha: float
    crosshair: str
    readout_bg: str
    logo: str  # resource filename
    # Per-joint curve colors J0..J5 — tuned for contrast on this background.
    joints: tuple


DARK = Theme(
    name="Dark",
    window="#232629",
    base="#1a1c1e",
    alt_base="#232629",
    text="#e6e8ea",
    dim_text="#8b9096",
    button="#32363b",
    border="#3c4147",
    plot_bg="#16181a",
    grid_alpha=0.22,
    crosshair="#9aa0a6",
    readout_bg="#101214",
    logo="logo_dark.png",
    joints=(
        "#4FC3F7",  # J0 cyan
        "#66E08A",  # J1 green
        "#FFB74D",  # J2 amber
        "#FF6B6B",  # J3 red
        "#C08CFF",  # J4 violet
        "#FFE066",  # J5 yellow
    ),
)

LIGHT = Theme(
    name="Light",
    window="#f2f4f7",
    base="#ffffff",
    alt_base="#f7f9fb",
    text="#12171d",
    dim_text="#5b6570",
    button="#e4e8ee",
    border="#c8d0d9",
    plot_bg="#ffffff",
    grid_alpha=0.16,
    crosshair="#5b6570",
    readout_bg="#eef1f5",
    logo="logo_light.png",
    joints=(
        "#0277BD",  # J0 blue
        "#1B7F3B",  # J1 green
        "#C25E00",  # J2 orange
        "#C62828",  # J3 red
        "#6A1B9A",  # J4 purple
        "#8D6E00",  # J5 dark yellow
    ),
)

THEMES = {"dark": DARK, "light": LIGHT}


def apply_theme(app: QtWidgets.QApplication, theme: Theme):
    """Apply a Fusion palette + stylesheet for the given theme."""
    app.setStyle("Fusion")
    p = QPalette()
    c = QColor

    p.setColor(QPalette.ColorRole.Window, c(theme.window))
    p.setColor(QPalette.ColorRole.WindowText, c(theme.text))
    p.setColor(QPalette.ColorRole.Base, c(theme.base))
    p.setColor(QPalette.ColorRole.AlternateBase, c(theme.alt_base))
    p.setColor(QPalette.ColorRole.Text, c(theme.text))
    p.setColor(QPalette.ColorRole.Button, c(theme.button))
    p.setColor(QPalette.ColorRole.ButtonText, c(theme.text))
    p.setColor(QPalette.ColorRole.ToolTipBase, c(theme.base))
    p.setColor(QPalette.ColorRole.ToolTipText, c(theme.text))
    p.setColor(QPalette.ColorRole.Highlight, c(BRAND_BLUE))
    p.setColor(QPalette.ColorRole.HighlightedText, c("#ffffff"))
    p.setColor(QPalette.ColorRole.Link, c(BRAND_BLUE))
    p.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, c(theme.dim_text)
    )
    p.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        c(theme.dim_text),
    )
    app.setPalette(p)

    app.setStyleSheet(f"""
        QGroupBox {{
            border: 1px solid {theme.border};
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 8px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: {theme.dim_text};
        }}
        QPushButton {{
            background: {theme.button};
            border: 1px solid {theme.border};
            border-radius: 4px;
            padding: 5px 12px;
        }}
        QPushButton:hover {{ border-color: {BRAND_BLUE}; }}
        QPushButton:pressed {{ background: {BRAND_BLUE}; color: #fff; }}
        QPushButton:disabled {{ color: {theme.dim_text}; }}
        QPushButton#primary {{
            background: {BRAND_BLUE};
            color: #ffffff;
            border: 1px solid {BRAND_BLUE};
            font-weight: 700;
        }}
        QPushButton#primary:disabled {{
            background: {theme.button};
            color: {theme.dim_text};
            border-color: {theme.border};
        }}
        QPushButton#danger {{
            background: #C62828; color: #fff; border: 1px solid #C62828;
            font-weight: 700;
        }}
        QPushButton#danger:disabled {{
            background: {theme.button};
            color: {theme.dim_text};
            border-color: {theme.border};
        }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background: {theme.base};
            border: 1px solid {theme.border};
            border-radius: 4px;
            padding: 4px 6px;
            selection-background-color: {BRAND_BLUE};
        }}
        QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border-color: {BRAND_BLUE};
        }}
        QTableWidget, QListWidget, QTreeWidget {{
            background: {theme.base};
            border: 1px solid {theme.border};
            border-radius: 4px;
            alternate-background-color: {theme.alt_base};
        }}
        QHeaderView::section {{
            background: {theme.button};
            border: none;
            border-bottom: 1px solid {theme.border};
            padding: 5px;
            font-weight: 600;
        }}
        QStatusBar {{ color: {theme.dim_text}; }}
        QToolTip {{
            background: {theme.base};
            color: {theme.text};
            border: 1px solid {BRAND_BLUE};
            padding: 4px;
        }}
        QSplitter::handle {{ background: {theme.border}; }}
        QLabel#tagline {{ color: {theme.dim_text}; }}
        QLabel#readout {{
            background: {theme.readout_bg};
            border: 1px solid {theme.border};
            border-radius: 4px;
            padding: 7px;
        }}
    """)
