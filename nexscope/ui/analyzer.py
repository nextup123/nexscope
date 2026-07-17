"""
Log analyser: load a recorded CSV and compare data flexibly.

Two grouping modes:
  • by OBJECT — pick object(s), pick joint(s): same object across joints.
  • by JOINT  — pick joint(s), pick object(s): different objects on one joint.

Both lists are multi-select, so every combination works (1 object x 6 joints,
1 object x 2 joints, 1 joint x N objects, ...).
"""

from __future__ import annotations

import csv
import os
import statistics

import pyqtgraph as pg
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt

from ..core.session import LogData, load_log
from .plotbase import CrosshairPlot
from .theme import Theme


class AnalyzerWindow(QtWidgets.QDialog):
    def __init__(self, theme: Theme, path: str | None = None, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.data: LogData | None = None
        self.setWindowTitle("NexScope — Log Analyser")
        self.resize(1240, 780)
        self._build()
        if path and os.path.exists(path):
            self.load(path)

    # ------------------------------------------------------------------ #
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)

        # ---- file row ---------------------------------------------------- #
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("CSV:"))
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("Path to a recorded log…")
        top.addWidget(self.path_edit, 1)
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        top.addWidget(browse)
        load = QtWidgets.QPushButton("Load")
        load.clicked.connect(lambda: self.load(self.path_edit.text()))
        top.addWidget(load)
        root.addLayout(top)

        # ---- info bar ---------------------------------------------------- #
        self.info = QtWidgets.QLabel("No log loaded.")
        self.info.setObjectName("tagline")
        root.addWidget(self.info)

        # ---- body -------------------------------------------------------- #
        body = QtWidgets.QHBoxLayout()

        # left controls
        ctl = QtWidgets.QVBoxLayout()
        ctl.setSpacing(6)

        mode_box = QtWidgets.QGroupBox("Group by")
        mv = QtWidgets.QVBoxLayout(mode_box)
        self.mode_object = QtWidgets.QRadioButton("Object — compare joints")
        self.mode_object.setToolTip(
            "Pick an object, see it across every joint.")
        self.mode_joint = QtWidgets.QRadioButton("Joint — compare objects")
        self.mode_joint.setToolTip(
            "Pick a joint, see multiple objects on it.")
        self.mode_object.setChecked(True)
        self.mode_object.toggled.connect(self._on_mode_changed)
        mv.addWidget(self.mode_object)
        mv.addWidget(self.mode_joint)
        ctl.addWidget(mode_box)

        self.primary_label = QtWidgets.QLabel("<b>Objects</b>")
        ctl.addWidget(self.primary_label)
        self.primary_list = QtWidgets.QListWidget()
        self.primary_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.primary_list.itemSelectionChanged.connect(self._replot)
        ctl.addWidget(self.primary_list, 2)

        self.secondary_label = QtWidgets.QLabel("<b>Joints</b>")
        ctl.addWidget(self.secondary_label)
        self.secondary_list = QtWidgets.QListWidget()
        self.secondary_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.secondary_list.itemSelectionChanged.connect(self._replot)
        ctl.addWidget(self.secondary_list, 2)

        sel = QtWidgets.QHBoxLayout()
        b_all = QtWidgets.QPushButton("Select all")
        b_all.clicked.connect(self._select_all_secondary)
        b_none = QtWidgets.QPushButton("None")
        b_none.clicked.connect(self.secondary_list.clearSelection)
        sel.addWidget(b_all)
        sel.addWidget(b_none)
        ctl.addLayout(sel)

        body.addLayout(ctl, 1)

        # right: plot + stats
        right = QtWidgets.QVBoxLayout()
        self.canvas = CrosshairPlot(self.theme)
        self.canvas.plot.setLabel("bottom", "Elapsed", units="s")
        self.canvas.plot.setLabel("left", "Value", units="counts")
        right.addWidget(self.canvas, 3)

        self.stats = QtWidgets.QTableWidget(0, 6)
        self.stats.setHorizontalHeaderLabels(
            ["Series", "Min", "Max", "Mean", "Std dev", "Samples"])
        self.stats.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.stats.verticalHeader().setVisible(False)
        self.stats.setAlternatingRowColors(True)
        self.stats.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stats.setMaximumHeight(150)
        right.addWidget(self.stats, 1)

        exp = QtWidgets.QHBoxLayout()
        exp.addStretch(1)
        b_png = QtWidgets.QPushButton("Export plot (PNG)…")
        b_png.clicked.connect(self._export_png)
        exp.addWidget(b_png)
        b_csv = QtWidgets.QPushButton("Export view (CSV)…")
        b_csv.setToolTip("Save only the currently plotted series.")
        b_csv.clicked.connect(self._export_csv)
        exp.addWidget(b_csv)
        right.addLayout(exp)

        body.addLayout(right, 3)
        root.addLayout(body, 1)

    # ------------------------------------------------------------------ #
    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.canvas.apply_theme(theme)
        self._replot()

    # ------------------------------------------------------------------ #
    def _browse(self):
        start = os.path.dirname(self.path_edit.text()) or "csv"
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open log", start if os.path.isdir(start) else "",
            "CSV files (*.csv)")
        if path:
            self.load(path)

    def load(self, path: str):
        path = path.strip()
        if not path or not os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, "Not found", f"No file: {path}")
            return
        try:
            self.data = load_log(path)
        except (ValueError, OSError) as e:
            QtWidgets.QMessageBox.critical(self, "Load failed", str(e))
            return

        self.path_edit.setText(path)
        d = self.data
        self.info.setText(
            f"{os.path.basename(path)} — {d.n_samples} samples · "
            f"{d.duration:.2f} s · mean rate {d.mean_rate:.1f} Hz · "
            f"{len(d.objects)} object(s) · {len(d.joints)} joint(s)")
        self._populate_lists()
        self._replot()

    # ------------------------------------------------------------------ #
    def _group_by_object(self) -> bool:
        return self.mode_object.isChecked()

    def _on_mode_changed(self):
        self._populate_lists()
        self._replot()

    def _populate_lists(self):
        if not self.data:
            return
        d = self.data
        by_obj = self._group_by_object()

        self.primary_label.setText("<b>Objects</b>" if by_obj else "<b>Joints</b>")
        self.secondary_label.setText("<b>Joints</b>" if by_obj else "<b>Objects</b>")

        self.primary_list.blockSignals(True)
        self.secondary_list.blockSignals(True)
        self.primary_list.clear()
        self.secondary_list.clear()

        def obj_item(k):
            it = QtWidgets.QListWidgetItem(f"{d.objects[k]}  [{d.obj_display[k]}]")
            it.setData(Qt.ItemDataRole.UserRole, ("obj", k))
            return it

        def joint_item(s):
            it = QtWidgets.QListWidgetItem(f"J{s}   (-p {s})")
            it.setData(Qt.ItemDataRole.UserRole, ("joint", s))
            return it

        if by_obj:
            for k in d.obj_order:
                self.primary_list.addItem(obj_item(k))
            for s in d.joints:
                self.secondary_list.addItem(joint_item(s))
        else:
            for s in d.joints:
                self.primary_list.addItem(joint_item(s))
            for k in d.obj_order:
                self.secondary_list.addItem(obj_item(k))

        if self.primary_list.count():
            self.primary_list.item(0).setSelected(True)
        for i in range(self.secondary_list.count()):
            self.secondary_list.item(i).setSelected(True)

        self.primary_list.blockSignals(False)
        self.secondary_list.blockSignals(False)

    def _select_all_secondary(self):
        for i in range(self.secondary_list.count()):
            self.secondary_list.item(i).setSelected(True)

    # ------------------------------------------------------------------ #
    def _selected_pairs(self) -> list[tuple[int, str]]:
        if not self.data:
            return []
        prim = [i.data(Qt.ItemDataRole.UserRole)
                for i in self.primary_list.selectedItems()]
        sec = [i.data(Qt.ItemDataRole.UserRole)
               for i in self.secondary_list.selectedItems()]
        by_obj = self._group_by_object()
        pairs = []
        for p in prim:
            for s in sec:
                slave, key = (s[1], p[1]) if by_obj else (p[1], s[1])
                if (slave, key) in self.data.values:
                    pairs.append((slave, key))
        return pairs

    def _replot(self):
        self.canvas.clear_plot()
        self.stats.setRowCount(0)
        if not self.data:
            return

        pairs = self._selected_pairs()
        by_obj = self._group_by_object()
        d = self.data
        self._plotted = []

        for n, (slave, key) in enumerate(pairs):
            xs, ys = d.series(slave, key)
            if not xs:
                continue
            if by_obj:
                # comparing joints -> color identifies the joint
                color = self.theme.joints[slave % len(self.theme.joints)]
            else:
                color = pg.intColor(n, hues=max(len(pairs), 6)).name()

            label = f"J{slave} · {d.objects[key]} [{d.obj_display[key]}]"
            self.canvas.plot.plot(xs, ys, pen=pg.mkPen(color, width=2),
                                  name=label)
            self.canvas.track_curve(label, color, xs, ys)
            self._plotted.append((slave, key, label, xs, ys))

        self._fill_stats()

    def _fill_stats(self):
        self.stats.setRowCount(len(self._plotted))
        for r, (_s, _k, label, _xs, ys) in enumerate(self._plotted):
            std = statistics.pstdev(ys) if len(ys) > 1 else 0.0
            vals = [
                label,
                f"{min(ys):,.3f}",
                f"{max(ys):,.3f}",
                f"{statistics.fmean(ys):,.3f}",
                f"{std:,.3f}",
                str(len(ys)),
            ]
            for c, v in enumerate(vals):
                self.stats.setItem(r, c, QtWidgets.QTableWidgetItem(v))

    # ------------------------------------------------------------------ #
    def _export_png(self):
        if not self._plotted:
            QtWidgets.QMessageBox.information(self, "Nothing to export",
                                              "Plot something first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export plot", "nexscope_plot.png", "PNG image (*.png)")
        if not path:
            return
        exporter = pg.exporters.ImageExporter(self.canvas.plot.plotItem)
        exporter.parameters()["width"] = 1920
        exporter.export(path)
        QtWidgets.QMessageBox.information(self, "Exported", f"Saved:\n{path}")

    def _export_csv(self):
        if not self._plotted:
            QtWidgets.QMessageBox.information(self, "Nothing to export",
                                              "Plot something first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export view", "nexscope_view.csv", "CSV files (*.csv)")
        if not path:
            return
        # union of all x values across plotted series, aligned by index
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["elapsed_s"] + [p[2] for p in self._plotted])
            # all series share the log's x grid; use the longest
            xs_ref = max((p[3] for p in self._plotted), key=len)
            lookups = []
            for _s, _k, _l, xs, ys in self._plotted:
                lookups.append(dict(zip(xs, ys)))
            for x in xs_ref:
                w.writerow([f"{x:.4f}"] + [lk.get(x, "") for lk in lookups])
        QtWidgets.QMessageBox.information(self, "Exported", f"Saved:\n{path}")
