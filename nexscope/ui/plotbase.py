"""
Shared plotting furniture: a themed pyqtgraph plot with a crosshair that
reports the exact value of every visible curve at the cursor's time.
"""

from __future__ import annotations

import bisect

import pyqtgraph as pg
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt

from .theme import Theme


def nearest_index(xs: list[float], target: float) -> int:
    """Index of the sample in sorted xs closest to target."""
    if not xs:
        return 0
    j = bisect.bisect_left(xs, target)
    if j <= 0:
        return 0
    if j >= len(xs):
        return len(xs) - 1
    return j if (xs[j] - target) < (target - xs[j - 1]) else j - 1


class CrosshairPlot(QtWidgets.QWidget):
    """
    A pyqtgraph PlotWidget plus a hover crosshair and a value readout panel.

    Subclasses/owners register curves via `track_curve` so hover can report
    them; call `reset_tracking` before rebuilding curves.
    """

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._tracked: list[dict] = []
        self._build()

    def _build(self):
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=self.theme.grid_alpha)
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setLabel("left", "Value")
        self.legend = self.plot.addLegend(offset=(10, 10))
        lay.addWidget(self.plot, 1)

        self.vline = pg.InfiniteLine(angle=90, movable=False)
        self.hline = pg.InfiniteLine(angle=0, movable=False)
        for ln in (self.vline, self.hline):
            self.plot.addItem(ln, ignoreBounds=True)
            ln.hide()

        self.readout = QtWidgets.QLabel("Hover the plot to read exact values.")
        self.readout.setObjectName("readout")
        self.readout.setTextFormat(Qt.TextFormat.RichText)
        self.readout.setWordWrap(True)
        self.readout.setMinimumHeight(64)
        self.readout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        mono = self.readout.font()
        mono.setFamily("monospace")
        self.readout.setFont(mono)
        lay.addWidget(self.readout)

        self._proxy = pg.SignalProxy(
            self.plot.scene().sigMouseMoved, rateLimit=60,
            slot=self._on_mouse_moved)

        self.apply_theme(self.theme)

    # ------------------------------------------------------------------ #
    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.plot.setBackground(theme.plot_bg)
        self.plot.showGrid(x=True, y=True, alpha=theme.grid_alpha)
        pen = pg.mkPen(theme.crosshair, width=1, style=Qt.PenStyle.DashLine)
        self.vline.setPen(pen)
        self.hline.setPen(pen)
        for ax in ("bottom", "left"):
            axis = self.plot.getAxis(ax)
            axis.setPen(pg.mkPen(theme.dim_text))
            axis.setTextPen(pg.mkPen(theme.text))

    # ------------------------------------------------------------------ #
    def reset_tracking(self):
        self._tracked = []

    def track_curve(self, label: str, color: str, xs, ys):
        self._tracked.append(
            {"label": label, "color": color, "xs": xs, "ys": ys})

    @property
    def tracked(self):
        return self._tracked

    def clear_plot(self):
        """Clear curves but keep the crosshair items alive."""
        self.plot.clear()
        self.legend = self.plot.addLegend(offset=(10, 10))
        for ln in (self.vline, self.hline):
            self.plot.addItem(ln, ignoreBounds=True)
            ln.hide()
        self.reset_tracking()

    # ------------------------------------------------------------------ #
    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if not self.plot.sceneBoundingRect().contains(pos):
            self.vline.hide()
            self.hline.hide()
            return
        if not self._tracked:
            return

        vb = self.plot.getPlotItem().vb
        pt = vb.mapSceneToView(pos)
        xv = pt.x()

        self.vline.setPos(xv)
        self.hline.setPos(pt.y())
        self.vline.show()
        self.hline.show()

        lines = [f"<b>t = {xv:.4f} s</b>"]
        for tr in self._tracked:
            xs = tr["xs"]
            if not xs:
                continue
            i = nearest_index(xs, xv)
            yv = tr["ys"][i]
            tv = xs[i]
            lines.append(
                f'<span style="color:{tr["color"]}">&#9632;</span> '
                f'{tr["label"]}: <b>{yv:,.3f}</b>'
                f'<span style="color:{self.theme.dim_text}"> @ {tv:.4f}s</span>'
            )
        self.readout.setText("<br>".join(lines))
