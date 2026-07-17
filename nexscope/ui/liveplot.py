"""
Live streaming plot: one curve per (slave, object), rolling time window.
"""

from __future__ import annotations

from collections import deque

import pyqtgraph as pg
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt

from ..core.model import SdoObject
from .plotbase import CrosshairPlot
from .theme import Theme

# Dash styles distinguish multiple objects sharing one joint's color.
DASHES = [
    Qt.PenStyle.SolidLine,
    Qt.PenStyle.DashLine,
    Qt.PenStyle.DotLine,
    Qt.PenStyle.DashDotLine,
    Qt.PenStyle.DashDotDotLine,
]


class LivePlot(QtWidgets.QWidget):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.curves: dict[tuple[int, str], pg.PlotDataItem] = {}
        self.buffers: dict[tuple[int, str], tuple[deque, deque]] = {}
        self.meta: dict[tuple[int, str], dict] = {}
        self.window_seconds = 30.0
        self._build()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.canvas = CrosshairPlot(self.theme)
        self.canvas.plot.setLabel("left", "Value", units="counts")
        lay.addWidget(self.canvas, 1)

        ctl = QtWidgets.QHBoxLayout()
        ctl.addWidget(QtWidgets.QLabel("Window (s):"))
        self.window_spin = QtWidgets.QDoubleSpinBox()
        self.window_spin.setRange(2.0, 3600.0)
        self.window_spin.setValue(self.window_seconds)
        self.window_spin.setToolTip("How much history the live plot keeps.")
        self.window_spin.valueChanged.connect(self._set_window)
        ctl.addWidget(self.window_spin)

        self.autoscale = QtWidgets.QCheckBox("Auto Y")
        self.autoscale.setChecked(True)
        ctl.addWidget(self.autoscale)

        self.pause = QtWidgets.QCheckBox("Pause")
        self.pause.setToolTip("Freeze the display. Recording continues.")
        ctl.addWidget(self.pause)
        ctl.addStretch(1)
        lay.addLayout(ctl)

    def _set_window(self, v):
        self.window_seconds = v

    # ------------------------------------------------------------------ #
    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.canvas.apply_theme(theme)
        # recolor existing curves by joint
        for (slave, key), curve in self.curves.items():
            m = self.meta[(slave, key)]
            color = theme.joints[slave % len(theme.joints)]
            m["color"] = color
            curve.setPen(pg.mkPen(color, width=2, style=m["dash"]))

    # ------------------------------------------------------------------ #
    def configure(self, objects: list[SdoObject], slaves: list[int]):
        """Rebuild curves for a new recording session."""
        self.canvas.clear_plot()
        self.curves.clear()
        self.buffers.clear()
        self.meta.clear()

        numeric = [o for o in objects if o.is_numeric]
        for oi, obj in enumerate(numeric):
            dash = DASHES[oi % len(DASHES)]
            for slave in slaves:
                color = self.theme.joints[slave % len(self.theme.joints)]
                label = f"J{slave} · {obj.name} [{obj.display}]"
                curve = self.canvas.plot.plot(
                    [], [], pen=pg.mkPen(color, width=2, style=dash),
                    name=label)
                k = (slave, obj.key)
                self.curves[k] = curve
                self.buffers[k] = (deque(), deque())
                self.meta[k] = {"label": label, "color": color, "dash": dash}

    def add_sample(self, sample):
        if self.pause.isChecked():
            return
        t = sample["t"]
        tmin = t - self.window_seconds

        for k, (xs, ys) in self.buffers.items():
            val = sample.get(k)
            if val is None:
                continue
            xs.append(t)
            ys.append(val)
            while xs and xs[0] < tmin:
                xs.popleft()
                ys.popleft()

        self.canvas.reset_tracking()
        for k, curve in self.curves.items():
            xs, ys = self.buffers[k]
            lx, ly = list(xs), list(ys)
            curve.setData(lx, ly)
            m = self.meta[k]
            self.canvas.track_curve(m["label"], m["color"], lx, ly)

        if self.autoscale.isChecked():
            self.canvas.plot.enableAutoRange(axis="y")

    def clear_data(self):
        for xs, ys in self.buffers.values():
            xs.clear()
            ys.clear()
        for curve in self.curves.values():
            curve.setData([], [])
        self.canvas.reset_tracking()
