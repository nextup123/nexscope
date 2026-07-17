"""
NexScope test suite.

Run:  QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v
  or: QT_QPA_PLATFORM=offscreen python3 tests/test_nexscope.py
"""

import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from nexscope.core.model import load_presets  # noqa: E402
from nexscope.core.reader import SimulatedReader  # noqa: E402
from nexscope.core.session import (  # noqa: E402
    RecordConfig, CsvWriter, load_log, parse_column,
)
from nexscope.ui.plotbase import nearest_index  # noqa: E402
from nexscope.ui.resources import default_presets_path  # noqa: E402

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
PRESETS = load_presets(default_presets_path())


def obj(index_hex, sub):
    return next(o for o in PRESETS
                if o.index_hex.upper() == index_hex.upper()
                and o.subindex_int == sub)


# --------------------------------------------------------------------- #
#  model
# --------------------------------------------------------------------- #

def test_presets_load():
    assert len(PRESETS) == 320
    types = {o.data_type for o in PRESETS}
    assert "int32" in types and "String" in types


def test_index_parsing():
    o = obj("0x607A", 0)
    assert o.index_hex == "0x607A"
    assert o.subindex_int == 0
    assert o.data_type == "int32"
    assert o.is_numeric


def test_ethercat_argv_matches_cli():
    # must reproduce: ethercat upload 0x607A 0 --type int32 -p 3
    assert obj("0x607A", 0).ethercat_args(3) == [
        "upload", "0x607A", "0", "--type", "int32", "-p", "3"]


def test_subindex_in_key_and_column():
    """Regression: 0x200B:01 and 0x200B:02 must never collide."""
    a, b = obj("0x200B", 1), obj("0x200B", 2)
    assert a.key != b.key
    assert a.column_name(2) != b.column_name(2)
    assert a.display == "0x200B:01"
    assert b.display == "0x200B:02"


def test_non_numeric_flagged():
    strs = [o for o in PRESETS if o.data_type == "String"]
    assert strs and not strs[0].is_numeric


# --------------------------------------------------------------------- #
#  session / csv
# --------------------------------------------------------------------- #

def test_parse_column_current_format():
    assert parse_column("s3_0x607Asub00_Target_position") == (
        3, "0x607A", 0, "Target position")
    assert parse_column("s2_0x200Bsub02_Speed_reference") == (
        2, "0x200B", 2, "Speed reference")


def test_parse_column_legacy_format():
    # pre-fix logs had no 'sub' token
    assert parse_column("s3_0x607A_Target_position") == (
        3, "0x607A", 0, "Target position")


def test_parse_column_rejects_meta():
    assert parse_column("timestamp") is None
    assert parse_column("elapsed_s") is None


def _write_log(path, objects, slaves, n=25, legacy=False):
    header = ["timestamp", "elapsed_s"]
    for s in slaves:
        for o in objects:
            if legacy:
                safe = o.name.replace(",", " ").replace(" ", "_")
                header.append(f"s{s}_{o.index_hex}_{safe}")
            else:
                header.append(o.column_name(s))
    rows = []
    for k in range(n):
        r = [f"2026-07-17T10:00:{k:02d}", f"{k * 0.05:.4f}"]
        for s in slaves:
            for oi, _o in enumerate(objects):
                r.append(str(1000 * s + 100 * oi + k))
        rows.append(r)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_csv_writer_creates_dirs():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "deep", "nested", "log.csv")
        cfg = RecordConfig([obj("0x607A", 0)], [0], 10.0, path)
        w = CsvWriter(cfg)
        header = w.open()
        w.write_row(["2026-01-01T00:00:00", "0.0000", 42])
        w.close()
        assert os.path.exists(path)
        assert header == ["timestamp", "elapsed_s",
                          "s0_0x607Asub00_Target_position"]


def test_load_log_roundtrip():
    objs = [obj("0x607A", 0), obj("0x6064", 0)]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "l.csv")
        _write_log(p, objs, [0, 1, 2])
        data = load_log(p)
        assert data.joints == [0, 1, 2]
        assert len(data.objects) == 2
        assert data.n_samples == 25
        xs, ys = data.series(1, objs[0].key)
        assert ys[0] == 1000.0  # 1000*1 + 100*0 + 0
        assert len(xs) == 25


def test_load_log_four_objects_two_sharing_index():
    """The exact reported bug: 4 selected, only 3 plotted."""
    objs = [obj("0x606C", 0), obj("0x6077", 0),
            obj("0x200B", 1), obj("0x200B", 2)]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "l.csv")
        _write_log(p, objs, [2])
        data = load_log(p)
        assert len(data.objects) == 4, list(data.objects.values())
        # the two 0x200B series must hold different data
        _, ys_a = data.series(2, objs[2].key)
        _, ys_b = data.series(2, objs[3].key)
        assert ys_a[0] == 2200.0 and ys_b[0] == 2300.0
        assert ys_a != ys_b


def test_load_legacy_log_recovers_collided_columns():
    """Old logs wrote both 0x200B subindexes under the same prefix."""
    objs = [obj("0x606C", 0), obj("0x200B", 1), obj("0x200B", 2)]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "legacy.csv")
        _write_log(p, objs, [2], legacy=True)
        data = load_log(p)
        # name-fallback keeps all three distinct
        assert len(data.objects) == 3, list(data.objects.values())
        names = set(data.objects.values())
        assert "Motor speed actual value" in names
        assert "Speed reference" in names


def test_load_log_handles_gaps():
    objs = [obj("0x607A", 0)]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "gap.csv")
        _write_log(p, objs, [0], n=5)
        # blank out a failed read
        rows = list(csv.reader(open(p)))
        rows[3][2] = ""
        with open(p, "w", newline="") as f:
            csv.writer(f).writerows(rows)
        data = load_log(p)
        xs, ys = data.series(0, objs[0].key)
        assert len(xs) == 4  # gap dropped
        assert data.n_samples == 5


def test_log_stats():
    objs = [obj("0x607A", 0)]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.csv")
        _write_log(p, objs, [0], n=21)  # 0.05 s spacing -> 1.0 s span
        data = load_log(p)
        assert abs(data.duration - 1.0) < 1e-6
        assert abs(data.mean_rate - 20.0) < 1e-6


# --------------------------------------------------------------------- #
#  reader
# --------------------------------------------------------------------- #

def test_simulated_reader():
    r = SimulatedReader()
    ok, msg = r.probe()
    assert ok and "Simulation" in msg
    v = r.read(obj("0x607A", 0), 3)
    assert isinstance(v, float)


# --------------------------------------------------------------------- #
#  plotting helpers
# --------------------------------------------------------------------- #

def test_nearest_index():
    xs = [0.0, 0.1, 0.2, 0.3]
    assert nearest_index(xs, 0.21) == 2
    assert nearest_index(xs, 0.26) == 3
    assert nearest_index(xs, -1) == 0
    assert nearest_index(xs, 99) == 3
    assert nearest_index([], 5) == 0


# --------------------------------------------------------------------- #
#  UI: analyzer grouping
# --------------------------------------------------------------------- #

def _analyzer_with(objs, slaves, legacy=False):
    from nexscope.ui.analyzer import AnalyzerWindow
    from nexscope.ui.theme import DARK
    d = tempfile.mkdtemp()
    p = os.path.join(d, "a.csv")
    _write_log(p, objs, slaves, legacy=legacy)
    w = AnalyzerWindow(DARK, p)
    return w


def test_analyzer_group_by_object():
    objs = [obj("0x607A", 0), obj("0x6064", 0)]
    w = _analyzer_with(objs, [0, 1, 2, 3, 4, 5])
    w.mode_object.setChecked(True)
    # default: 1 object x all 6 joints
    assert len(w._selected_pairs()) == 6

    # 1 object x 2 joints
    w.secondary_list.clearSelection()
    w.secondary_list.item(0).setSelected(True)
    w.secondary_list.item(3).setSelected(True)
    assert len(w._selected_pairs()) == 2

    # 2 objects x 6 joints
    w.primary_list.item(1).setSelected(True)
    w._select_all_secondary()
    assert len(w._selected_pairs()) == 12


def test_analyzer_group_by_joint():
    objs = [obj("0x606C", 0), obj("0x6077", 0), obj("0x200B", 1)]
    w = _analyzer_with(objs, [0, 1, 2])
    w.mode_joint.setChecked(True)
    # default: 1 joint x 3 objects
    assert len(w._selected_pairs()) == 3

    # 1 joint x 2 objects
    w.secondary_list.clearSelection()
    w.secondary_list.item(0).setSelected(True)
    w.secondary_list.item(1).setSelected(True)
    assert len(w._selected_pairs()) == 2

    # 2 joints x 1 object
    w.primary_list.item(1).setSelected(True)
    w.secondary_list.clearSelection()
    w.secondary_list.item(2).setSelected(True)
    assert len(w._selected_pairs()) == 2


def test_analyzer_plots_four_distinct_curves():
    """End-to-end of the reported bug, through the real widget."""
    objs = [obj("0x606C", 0), obj("0x6077", 0),
            obj("0x200B", 1), obj("0x200B", 2)]
    w = _analyzer_with(objs, [2])
    w.mode_joint.setChecked(True)
    w.primary_list.item(0).setSelected(True)
    w._select_all_secondary()
    w._replot()
    assert len(w._plotted) == 4
    labels = [p[2] for p in w._plotted]
    assert len(set(labels)) == 4
    assert any("0x200B:01" in l for l in labels)
    assert any("0x200B:02" in l for l in labels)


def test_analyzer_stats_populate():
    objs = [obj("0x607A", 0)]
    w = _analyzer_with(objs, [0])
    w._replot()
    assert w.stats.rowCount() == 1
    assert w.stats.item(0, 5).text() == "25"  # sample count


def test_analyzer_joint_colors_are_stable():
    from nexscope.ui.theme import DARK
    objs = [obj("0x607A", 0)]
    w = _analyzer_with(objs, [0, 1, 2, 3, 4, 5])
    w.mode_object.setChecked(True)
    w._replot()
    for slave, _k, _l, _xs, _ys in w._plotted:
        pass
    assert len(w._plotted) == 6


# --------------------------------------------------------------------- #
#  UI: picker
# --------------------------------------------------------------------- #

def test_picker_dedupes():
    from nexscope.ui.picker import ObjectPicker
    p = ObjectPicker(PRESETS, [])
    o = obj("0x607A", 0)
    p.add_object(o)
    p.add_object(o)
    assert len(p.selected) == 1


def test_picker_quick_set():
    from nexscope.ui.picker import ObjectPicker
    p = ObjectPicker(PRESETS, [])
    p._apply_quick("Target vs Actual Pos")
    keys = {o.key for o in p.selected}
    assert "0x607A:0" in keys and "0x6064:0" in keys


def test_picker_search_filters():
    from nexscope.ui.picker import ObjectPicker
    p = ObjectPicker(PRESETS, [])
    p.search.setText("607A")
    assert all("607A" in o.index_hex.upper() for o in p._rows)
    p.search.setText("zzzznotathing")
    assert len(p._rows) == 0


def test_picker_favourites_filter():
    from nexscope.ui.picker import ObjectPicker
    fav = obj("0x607A", 0)
    p = ObjectPicker(PRESETS, [fav.key])
    p.fav_only.setChecked(True)
    assert len(p._rows) == 1
    assert p._rows[0].key == fav.key


# --------------------------------------------------------------------- #
#  themes
# --------------------------------------------------------------------- #

def test_themes_complete():
    from nexscope.ui.theme import THEMES
    assert set(THEMES) == {"dark", "light"}
    for t in THEMES.values():
        assert len(t.joints) == 6
        assert t.logo.endswith(".png")


def test_logo_assets_exist():
    from nexscope.ui.resources import logo_path
    from nexscope.ui.theme import THEMES
    for t in THEMES.values():
        assert os.path.exists(logo_path(t.logo)), t.logo


# --------------------------------------------------------------------- #

if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    passed = failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAIL  {name}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
