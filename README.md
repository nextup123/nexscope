# NexScope

**EtherCAT SDO Oscilloscope & Logger** — Nextup Robotics Pvt Ltd

Live-plots and records SDO objects from the 6 SV660 drives of the Nextup
6-DOF cobot, then lets you slice the recorded data any way you need.

It wraps the IgH CLI command you already use:

```
ethercat upload 0x607A 0 --type int32 -p 3
```

---

## Install

```bash
# runtime deps
pip install PyQt6 pyqtgraph

# Qt needs this on Ubuntu, or you get "could not load the xcb platform plugin"
sudo apt install libxcb-cursor0
```

Optionally install the package itself (gives you a `nexscope` command):

```bash
pip install -e .
```

## Run

```bash
python3 run_nexscope.py              # talks to the real EtherCAT master
python3 run_nexscope.py --simulate   # synthetic data, no hardware needed
python3 run_nexscope.py --theme light
python3 -m nexscope --simulate       # equivalent
nexscope                             # if pip-installed
```

Options:

| Flag | Meaning |
|---|---|
| `--simulate` | Synthetic sine data. Test the UI with no master. |
| `--presets PATH` | Use a different SDO dictionary JSON. |
| `--theme dark\|light` | Override the saved theme for this run. |

## Workflow

1. **Pick joints** — J0–J5 map to `-p 0` … `-p 5`.
2. **Find objects** — search by name or index (`position`, `607A`, `velocity`).
   Double-click the ★ column to favourite one; tick **★ Favourites** to filter.
   **Quick sets** add common pairs in one click.
3. **Set the rate** — the estimate line shows the SDO-bound ceiling and warns
   if your target exceeds it.
4. **Start recording** — live plot streams; hover it for exact values. The
   status bar shows the *achieved* rate and failed-read count.
5. **Analyse** — opens automatically when you stop, or via **Analyse a log…**.

Your theme, rate, output folder, joint selection, favourites and last object
set all persist between runs.

## Log Analyser

Two grouping modes:

- **Group by Object** — pick object(s) on top, joint(s) below. Compares *one
  object across joints* (Target position on all 6, or just J0 vs J3). Curves
  are colored per joint, consistently.
- **Group by Joint** — pick joint(s) on top, object(s) below. Compares
  *objects on one joint* (Target vs Actual on J3).

Both lists are multi-select, so any combination works: 1×6, 1×2, 1×N, 2×1.

Also included:
- **Hover crosshair** — exact decimal value of every visible curve at the
  cursor's time, snapped to the nearest real sample.
- **Stats table** — min / max / mean / std dev / sample count per series.
- **Export** — PNG of the plot, or CSV of just the currently plotted series.

## CSV format

```
timestamp, elapsed_s, s2_0x200Bsub01_Motor_speed_actual_value, ...
```

- `timestamp` — wall-clock ISO (ms precision)
- `elapsed_s` — seconds since record start; the plot X axis
- one column per (joint, object); empty cell = failed/timed-out read

The **subindex is encoded in the column name** (`sub01`). This matters:
`0x200B:01` (Motor speed actual value) and `0x200B:02` (Speed reference) share
an index, and without the subindex they collide into one column — you'd select
4 objects and only see 3 curves. Logs written before this fix are still
readable; the analyser disambiguates the collided pair by name.

## The SDO rate ceiling

Each value costs one `ethercat upload` — a process spawn plus a mailbox
round-trip, roughly 1–5 ms. A sweep reads every (joint × object) pair
serially, so:

| Selection | Reads/sweep | Realistic ceiling |
|---|---|---|
| 2 objects × 1 joint | 2 | ~150 Hz |
| 2 objects × 6 joints | 12 | ~25 Hz |
| 4 objects × 6 joints | 24 | ~14 Hz |

Setting a higher target won't help — the app shows both the estimate and the
achieved rate so the gap is visible rather than silent. Sample spacing will
also jitter, which is why the hover readout reports the *actual sample time*
next to each value rather than the raw cursor position.

For genuinely high-rate, low-jitter capture you'd log **PDO** (cyclic process
data) instead of SDO mailbox reads. NexScope targets tuning and verification in
the tens-of-Hz range, where SDO polling is appropriate.

## Project layout

```
nexscope/
├── run_nexscope.py          # launcher
├── pyproject.toml
├── nexscope/
│   ├── app.py               # entry point, CLI args
│   ├── core/                # no Qt widgets — testable in isolation
│   │   ├── model.py         # SdoObject, preset loading
│   │   ├── reader.py        # ethercat CLI + simulated backends
│   │   ├── recorder.py      # QThread polling loop
│   │   ├── session.py       # CSV write/read, LogData
│   │   └── settings.py      # persistence
│   ├── ui/
│   │   ├── theme.py         # dark/light palettes, brand colors
│   │   ├── header.py        # logo + theme toggle
│   │   ├── picker.py        # object search/selection
│   │   ├── plotbase.py      # shared crosshair plot
│   │   ├── liveplot.py      # streaming plot
│   │   ├── analyzer.py      # log analysis window
│   │   └── mainwindow.py
│   └── resources/           # logos, sdo_presets.json
└── tests/
```

`core/` holds no Qt widgets, so it's testable without a display.

## Tests

```bash
QT_QPA_PLATFORM=offscreen python3 tests/test_nexscope.py
# or
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -v
```

27 tests covering the model, CSV round-trip, legacy-log compatibility, the
subindex-collision regression, grouping logic, and theming.

## Troubleshooting

**"Could not load the Qt platform plugin xcb"**
`sudo apt install libxcb-cursor0`

**"'ethercat' not found on PATH"**
The IgH master isn't installed or isn't on PATH. Use `--simulate` to work on
the UI meanwhile.

**Achieved rate far below target**
Expected — see the rate ceiling section. Reduce objects or joints.

**Values look like a wrapping sawtooth**
The object is probably being read with too narrow a type. Position objects are
`int32`; reading them as `int16` truncates to the low 16 bits. NexScope takes
the type straight from the preset JSON, so this shouldn't happen unless the
dictionary entry itself is wrong.
