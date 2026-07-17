"""
Background recording thread.

Polls every (slave, object) pair in a sweep, writes each sweep to CSV, and
emits it for live plotting. Runs off the GUI thread so the UI stays responsive
while blocking on subprocess reads.
"""

from __future__ import annotations

import time
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal

from .reader import BaseReader
from .session import CsvWriter, RecordConfig


class Sample(dict):
    """One sweep: {'t': float, 'wall': str, (slave, obj_key): value|None}."""


class RecorderThread(QThread):
    sample_ready = pyqtSignal(object)  # Sample
    stats_ready = pyqtSignal(float, int, int)  # achieved_hz, sweeps, failed
    error = pyqtSignal(str)
    finished_recording = pyqtSignal(str)  # csv path ('' on failure)

    def __init__(self, reader: BaseReader, cfg: RecordConfig):
        super().__init__()
        self.reader = reader
        self.cfg = cfg
        self._stop = False
        self._writer = CsvWriter(cfg)

    def stop(self):
        self._stop = True

    def run(self):
        try:
            self._writer.open()
        except OSError as e:
            self.error.emit(f"Cannot open CSV: {e}")
            self.finished_recording.emit("")
            return

        period = 1.0 / self.cfg.target_hz if self.cfg.target_hz > 0 else 0.0
        t0 = time.time()
        sweeps = 0
        failed = 0
        last_emit = t0
        since_emit = 0

        try:
            while not self._stop:
                sweep_start = time.time()
                elapsed = sweep_start - t0

                sample = Sample()
                sample["t"] = elapsed
                sample["wall"] = datetime.now().isoformat(timespec="milliseconds")

                row = [sample["wall"], f"{elapsed:.4f}"]
                for slave in self.cfg.slaves:
                    for obj in self.cfg.objects:
                        val = self.reader.read(obj, slave)
                        if val is None:
                            failed += 1
                            row.append("")
                        else:
                            row.append(val)
                        sample[(slave, obj.key)] = val

                self._writer.write_row(row)
                self.sample_ready.emit(sample)

                sweeps += 1
                since_emit += 1

                now = time.time()
                if now - last_emit >= 0.25:
                    hz = since_emit / (now - last_emit)
                    self.stats_ready.emit(hz, sweeps, failed)
                    last_emit = now
                    since_emit = 0

                if period > 0:
                    left = period - (time.time() - sweep_start)
                    if left > 0:
                        time.sleep(left)
        except Exception as e:  # noqa: BLE001 - surface anything to the UI
            self.error.emit(f"Recorder crashed: {e}")
        finally:
            self._writer.close()
            self.finished_recording.emit(self.cfg.csv_path)
