"""
NexScope main window.
"""

from __future__ import annotations

import os
from datetime import datetime

from PyQt6 import QtGui, QtWidgets
from PyQt6.QtCore import Qt

from .. import __app_name__, __company__
from ..core.model import SdoObject
from ..core.reader import BaseReader, EthercatReader
from ..core.recorder import RecorderThread
from ..core.session import RecordConfig
from ..core.settings import Settings
from .analyzer import AnalyzerWindow
from .header import Header
from .liveplot import LivePlot
from .picker import ObjectPicker
from .theme import THEMES, Theme

NUM_SLAVES = 6

# Rough cost of one shelled-out `ethercat upload` (process spawn + mailbox).
EST_READ_MS = 3.0


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, presets: list[SdoObject], reader: BaseReader,
                 simulate: bool, settings: Settings):
        super().__init__()
        self.presets = presets
        self.reader = reader
        self.simulate = simulate
        self.settings = settings
        self.recorder: RecorderThread | None = None
        self.analyzer: AnalyzerWindow | None = None

        self.theme_key = settings.theme
        self.theme: Theme = THEMES[self.theme_key]

        self.setWindowTitle(
            f"{__app_name__} — {__company__}"
            + ("   [SIMULATION]" if simulate else ""))
        self.resize(1320, 880)

        self._build()
        self._restore()
        self._probe_backend()

    # ------------------------------------------------------------------ #
    def _build(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setSpacing(8)

        # ---- header ----------------------------------------------------- #
        self.header = Header(self.theme, self.theme_key)
        self.header.theme_toggled.connect(self._set_theme)
        root.addWidget(self.header)

        # ---- config ----------------------------------------------------- #
        cfg = QtWidgets.QGroupBox("Recording configuration")
        g = QtWidgets.QGridLayout(cfg)
        g.setHorizontalSpacing(12)

        g.addWidget(QtWidgets.QLabel("Joints:"), 0, 0)
        srow = QtWidgets.QHBoxLayout()
        self.slave_checks = []
        for s in range(NUM_SLAVES):
            cb = QtWidgets.QCheckBox(f"J{s}")
            cb.setToolTip(f"EtherCAT slave position {s}  (-p {s})")
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_estimate)
            self.slave_checks.append(cb)
            srow.addWidget(cb)
        b_all = QtWidgets.QPushButton("All")
        b_all.clicked.connect(lambda: self._set_all_slaves(True))
        b_none = QtWidgets.QPushButton("None")
        b_none.clicked.connect(lambda: self._set_all_slaves(False))
        srow.addWidget(b_all)
        srow.addWidget(b_none)
        srow.addStretch(1)
        g.addLayout(srow, 0, 1, 1, 3)

        g.addWidget(QtWidgets.QLabel("Target rate (Hz):"), 1, 0)
        self.rate_spin = QtWidgets.QDoubleSpinBox()
        self.rate_spin.setRange(0.5, 500.0)
        self.rate_spin.setDecimals(1)
        self.rate_spin.setToolTip(
            "Best effort. SDO mailbox reads are slow — with several objects "
            "across 6 slaves the achieved rate may be far below this.")
        self.rate_spin.valueChanged.connect(self._update_estimate)
        g.addWidget(self.rate_spin, 1, 1)

        g.addWidget(QtWidgets.QLabel("Output folder:"), 1, 2)
        out_row = QtWidgets.QHBoxLayout()
        self.out_edit = QtWidgets.QLineEdit()
        out_row.addWidget(self.out_edit, 1)
        b_out = QtWidgets.QPushButton("…")
        b_out.setFixedWidth(32)
        b_out.clicked.connect(self._pick_out_dir)
        out_row.addWidget(b_out)
        g.addLayout(out_row, 1, 3)

        root.addWidget(cfg)

        # ---- splitter: picker / live ------------------------------------ #
        split = QtWidgets.QSplitter(Qt.Orientation.Vertical)

        pick_box = QtWidgets.QGroupBox("SDO objects")
        pv = QtWidgets.QVBoxLayout(pick_box)
        self.picker = ObjectPicker(self.presets, self.settings.favourites)
        self.picker.selection_changed.connect(self._update_estimate)
        pv.addWidget(self.picker)
        split.addWidget(pick_box)

        live_box = QtWidgets.QGroupBox("Live plot")
        lv = QtWidgets.QVBoxLayout(live_box)
        self.live = LivePlot(self.theme)
        lv.addWidget(self.live)
        split.addWidget(live_box)
        split.setSizes([340, 520])
        root.addWidget(split, 1)

        # ---- controls --------------------------------------------------- #
        ctl = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("●  Start recording")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QtWidgets.QPushButton("■  Stop")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        self.analyze_btn = QtWidgets.QPushButton("Analyse a log…")
        self.analyze_btn.clicked.connect(lambda: self._open_analyzer(None))

        ctl.addWidget(self.start_btn)
        ctl.addWidget(self.stop_btn)
        ctl.addWidget(self.analyze_btn)
        ctl.addStretch(1)
        self.estimate = QtWidgets.QLabel()
        self.estimate.setObjectName("tagline")
        ctl.addWidget(self.estimate)
        root.addLayout(ctl)

        self.status = self.statusBar()

    # ------------------------------------------------------------------ #
    def _restore(self):
        self.rate_spin.setValue(self.settings.rate_hz)
        self.out_edit.setText(self.settings.out_dir)
        saved = set(self.settings.slaves)
        for i, cb in enumerate(self.slave_checks):
            cb.setChecked(i in saved)
        for key in self.settings.last_objects:
            self.picker.add_by_key(key)
        geo = self.settings.load_geometry()
        if geo:
            self.restoreGeometry(geo)
        self._update_estimate()

    def _probe_backend(self):
        ok, msg = self.reader.probe()
        self.status.showMessage(msg)
        if not ok:
            self.status.showMessage("⚠  " + msg)

    # ------------------------------------------------------------------ #
    def _set_theme(self, key: str):
        self.theme_key = key
        self.theme = THEMES[key]
        self.settings.theme = key

        from .theme import apply_theme
        apply_theme(QtWidgets.QApplication.instance(), self.theme)

        self.header.apply_theme(self.theme)
        self.live.apply_theme(self.theme)
        if self.analyzer:
            self.analyzer.apply_theme(self.theme)

    # ------------------------------------------------------------------ #
    def _set_all_slaves(self, on: bool):
        for cb in self.slave_checks:
            cb.setChecked(on)

    def _selected_slaves(self) -> list[int]:
        return [i for i, cb in enumerate(self.slave_checks) if cb.isChecked()]

    def _pick_out_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Output folder", self.out_edit.text() or ".")
        if d:
            self.out_edit.setText(d)

    def _update_estimate(self):
        n_obj = len(self.picker.selected)
        n_sl = len(self._selected_slaves())
        reads = n_obj * n_sl
        if reads == 0:
            self.estimate.setText("Select objects and joints to begin.")
            return
        ceiling = 1000.0 / (reads * EST_READ_MS)
        want = self.rate_spin.value()
        warn = "  ⚠ target exceeds ceiling" if want > ceiling else ""
        self.estimate.setText(
            f"{n_obj} obj × {n_sl} joints = {reads} reads/sweep · "
            f"est. ceiling ≈ {ceiling:.1f} Hz{warn}")

    def _csv_path(self) -> str:
        folder = self.out_edit.text().strip() or "csv"
        return os.path.join(
            folder, f"sdo_log_{datetime.now():%Y%m%d_%H%M%S}.csv")

    # ------------------------------------------------------------------ #
    def _start(self):
        objects = list(self.picker.selected)
        slaves = self._selected_slaves()
        if not objects:
            QtWidgets.QMessageBox.warning(
                self, "No objects", "Add at least one SDO object to record.")
            return
        if not slaves:
            QtWidgets.QMessageBox.warning(
                self, "No joints", "Select at least one joint.")
            return

        cfg = RecordConfig(objects=objects, slaves=slaves,
                           target_hz=self.rate_spin.value(),
                           csv_path=self._csv_path())

        self.live.configure(objects, slaves)
        self.live.clear_data()

        self.recorder = RecorderThread(self.reader, cfg)
        self.recorder.sample_ready.connect(self.live.add_sample)
        self.recorder.stats_ready.connect(self._on_stats)
        self.recorder.error.connect(self._on_error)
        self.recorder.finished_recording.connect(self._on_finished)
        self.recorder.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_config_enabled(False)
        self.status.showMessage(f"Recording → {cfg.csv_path}")

    def _stop(self):
        if self.recorder:
            self.recorder.stop()
            self.stop_btn.setEnabled(False)
            self.status.showMessage("Stopping…")

    def _set_config_enabled(self, on: bool):
        self.rate_spin.setEnabled(on)
        self.out_edit.setEnabled(on)
        self.picker.setEnabled(on)
        for cb in self.slave_checks:
            cb.setEnabled(on)

    # ------------------------------------------------------------------ #
    def _on_stats(self, hz, sweeps, failed):
        fail = f"   ·   failed reads: {failed}" if failed else ""
        self.status.showMessage(
            f"Recording…   {hz:.1f} Hz achieved   ·   {sweeps} sweeps{fail}")

    def _on_error(self, msg):
        QtWidgets.QMessageBox.critical(self, "Recorder error", msg)

    def _on_finished(self, path):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_config_enabled(True)
        self.recorder = None
        if not path:
            self.status.showMessage("Recording failed.")
            return
        self.status.showMessage(f"Saved: {path}")
        r = QtWidgets.QMessageBox.question(
            self, "Recording complete",
            f"Saved to:\n{path}\n\nOpen it in the Log Analyser?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No)
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            self._open_analyzer(path)

    def _open_analyzer(self, path):
        self.analyzer = AnalyzerWindow(
            self.theme, path if isinstance(path, str) else None, self)
        self.analyzer.exec()

    # ------------------------------------------------------------------ #
    def closeEvent(self, ev):
        if self.recorder:
            self.recorder.stop()
            self.recorder.wait(2000)
        # persist
        self.settings.rate_hz = self.rate_spin.value()
        self.settings.out_dir = self.out_edit.text().strip() or "csv"
        self.settings.slaves = self._selected_slaves()
        self.settings.favourites = sorted(self.picker.favourites)
        self.settings.last_objects = [o.key for o in self.picker.selected]
        self.settings.save_geometry(self.saveGeometry())
        ev.accept()
