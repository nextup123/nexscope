"""
Recording session: CSV writing, and reading logs back for analysis.

CSV layout:
    timestamp, elapsed_s, s{slave}_{index}sub{sub}_{name}, ...

`timestamp` is wall-clock ISO (ms). `elapsed_s` is seconds since record start
and is the X axis for all plots.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field

from .model import SdoObject


# --------------------------------------------------------------------------- #
#  Writing
# --------------------------------------------------------------------------- #


@dataclass
class RecordConfig:
    objects: list[SdoObject]
    slaves: list[int]
    target_hz: float
    csv_path: str

    @property
    def reads_per_sweep(self) -> int:
        return len(self.objects) * len(self.slaves)


class CsvWriter:
    """Streams sweeps to a CSV, creating parent dirs as needed."""

    def __init__(self, cfg: RecordConfig):
        self.cfg = cfg
        self._f = None
        self._w = None

    def open(self):
        parent = os.path.dirname(self.cfg.csv_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._f = open(self.cfg.csv_path, "w", newline="")
        self._w = csv.writer(self._f)
        header = ["timestamp", "elapsed_s"]
        for slave in self.cfg.slaves:
            for obj in self.cfg.objects:
                header.append(obj.column_name(slave))
        self._w.writerow(header)
        return header

    def write_row(self, row: list):
        self._w.writerow(row)

    def close(self):
        if self._f:
            self._f.flush()
            self._f.close()
            self._f = None


# --------------------------------------------------------------------------- #
#  Reading back
# --------------------------------------------------------------------------- #


@dataclass
class ColumnMeta:
    slave: int
    obj_key: str  # 'index:sub' — unique
    index_hex: str
    subindex: int
    name: str
    display: str  # '0x200B:01'
    col: int


@dataclass
class LogData:
    """A parsed CSV log, indexed for flexible plotting."""

    path: str = ""
    header: list[str] = field(default_factory=list)
    x: list[float] = field(default_factory=list)  # elapsed_s
    wall: list[str] = field(default_factory=list)  # ISO timestamps
    # values[(slave, obj_key)] = list[float | None] parallel to x
    values: dict[tuple[int, str], list] = field(default_factory=dict)
    joints: list[int] = field(default_factory=list)
    # obj_order preserves first-seen order; objects maps key -> name
    obj_order: list[str] = field(default_factory=list)
    objects: dict[str, str] = field(default_factory=dict)
    obj_display: dict[str, str] = field(default_factory=dict)

    @property
    def n_samples(self) -> int:
        return len(self.x)

    @property
    def duration(self) -> float:
        return (self.x[-1] - self.x[0]) if len(self.x) > 1 else 0.0

    @property
    def mean_rate(self) -> float:
        d = self.duration
        return (len(self.x) - 1) / d if d > 0 else 0.0

    def series(self, slave: int, obj_key: str):
        """Return (xs, ys) with gaps (failed reads) dropped."""
        vals = self.values.get((slave, obj_key))
        if vals is None:
            return [], []
        xs, ys = [], []
        for x, v in zip(self.x, vals):
            if v is None:
                continue
            xs.append(x)
            ys.append(v)
        return xs, ys


def parse_column(col: str):
    """
    Parse a data column name.

    Current:  's3_0x607Asub00_Target_position'
    Legacy:   's3_0x607A_Target_position'   (pre-subindex-fix logs)

    Returns (slave, index_hex, subindex, name) or None.
    """
    if not col.startswith("s"):
        return None
    parts = col.split("_", 2)
    if len(parts) < 3:
        return None
    try:
        slave = int(parts[0][1:])
    except ValueError:
        return None

    token = parts[1]  # '0x607Asub00' or legacy '0x607A'
    name = parts[2].replace("_", " ").strip()

    if "sub" in token:
        index_hex, _, sub_txt = token.partition("sub")
        try:
            sub = int(sub_txt)
        except ValueError:
            sub = 0
    else:
        index_hex, sub = token, 0

    return slave, index_hex, sub, name


def load_log(path: str) -> LogData:
    """Read a recorded CSV into a LogData ready for plotting."""
    with open(path) as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError("Empty CSV")

    data = LogData(path=path, header=rows[0])
    body = rows[1:]

    # --- x axis + wall clock ---
    for r in body:
        try:
            data.x.append(float(r[1]))
        except (ValueError, IndexError):
            data.x.append(float("nan"))
        data.wall.append(r[0] if r else "")

    # --- map columns -> object keys ---
    metas: list[ColumnMeta] = []
    seen: dict[tuple[int, str], ColumnMeta] = {}

    for ci, col in enumerate(data.header):
        parsed = parse_column(col)
        if parsed is None:
            continue
        slave, index_hex, sub, name = parsed
        obj_key = f"{index_hex}:{sub}"
        display = f"{index_hex}:{sub:02d}"

        # Legacy logs omit the subindex, so two subindexes of one index both
        # parse to ':0' and would overwrite each other. They still differ by
        # NAME, so fall back to that to keep the data recoverable.
        if (slave, obj_key) in seen and seen[(slave, obj_key)].name != name:
            obj_key = f"{index_hex}:{name}"
            display = index_hex

        m = ColumnMeta(slave, obj_key, index_hex, sub, name, display, ci)
        metas.append(m)
        seen[(slave, obj_key)] = m

    # --- build value series ---
    joints = set()
    for m in metas:
        joints.add(m.slave)
        if m.obj_key not in data.objects:
            data.objects[m.obj_key] = m.name
            data.obj_display[m.obj_key] = m.display
            data.obj_order.append(m.obj_key)

        col_vals = []
        for r in body:
            try:
                col_vals.append(float(r[m.col]))
            except (ValueError, IndexError):
                col_vals.append(None)
        data.values[(m.slave, m.obj_key)] = col_vals

    data.joints = sorted(joints)
    return data
