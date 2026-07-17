"""
Branded application header: Nextup Robotics logo, app name, theme switch.
"""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, pyqtSignal

from .. import __app_name__, __tagline__, __version__
from .resources import logo_path
from .theme import BRAND_BLUE, Theme

LOGO_HEIGHT = 34


class Header(QtWidgets.QWidget):
    theme_toggled = pyqtSignal(str)  # 'dark' | 'light'

    def __init__(self, theme: Theme, theme_key: str, parent=None):
        super().__init__(parent)
        self._theme_key = theme_key
        self._build()
        self.apply_theme(theme)

    def _build(self):
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 6)
        lay.setSpacing(12)

        self.logo = QtWidgets.QLabel()
        self.logo.setFixedHeight(LOGO_HEIGHT)
        lay.addWidget(self.logo)

        # divider
        self.rule = QtWidgets.QFrame()
        self.rule.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        self.rule.setFixedHeight(LOGO_HEIGHT - 6)
        lay.addWidget(self.rule)

        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(0)
        self.title = QtWidgets.QLabel(__app_name__)
        f = self.title.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        self.title.setFont(f)
        self.tagline = QtWidgets.QLabel(f"{__tagline__} · v{__version__}")
        self.tagline.setObjectName("tagline")
        tf = self.tagline.font()
        tf.setPointSize(max(tf.pointSize() - 1, 7))
        self.tagline.setFont(tf)
        title_box.addWidget(self.title)
        title_box.addWidget(self.tagline)
        lay.addLayout(title_box)

        lay.addStretch(1)

        self.theme_btn = QtWidgets.QToolButton()
        self.theme_btn.setCheckable(False)
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setAutoRaise(True)
        self.theme_btn.setToolTip("Toggle dark / light theme")
        self.theme_btn.clicked.connect(self._toggle)
        lay.addWidget(self.theme_btn)

    def _toggle(self):
        self._theme_key = "light" if self._theme_key == "dark" else "dark"
        self.theme_toggled.emit(self._theme_key)

    def apply_theme(self, theme: Theme):
        # swap logo variant to suit the background
        pm = QtGui.QPixmap(logo_path(theme.logo))
        if not pm.isNull():
            self.logo.setPixmap(
                pm.scaledToHeight(
                    LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation
                )
            )
        self.rule.setStyleSheet(f"color: {theme.border};")
        # sun when dark (click for light), moon when light
        self.theme_btn.setText("☀" if theme.name == "Dark" else "☾")
        bf = self.theme_btn.font()
        bf.setPointSize(14)
        self.theme_btn.setFont(bf)
        self.theme_btn.setStyleSheet(
            f"QToolButton {{ color: {theme.dim_text}; border: none; "
            f"padding: 4px 8px; }}"
            f"QToolButton:hover {{ color: {BRAND_BLUE}; }}"
        )
