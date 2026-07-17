# Changelog

## 1.0.0 — NexScope

First release under the NexScope name; restructured from the single-file
`sdo_monitor.py` prototype into a maintainable package.

### Fixed
- **SDO subindex collision.** Column names used only the object index, so
  objects sharing an index with different subindexes (e.g. `0x200B:01` Motor
  speed actual value and `0x200B:02` Speed reference) collided into a single
  CSV column and the second silently overwrote the first — selecting 4 objects
  produced only 3 curves. Subindex is now part of the column name and every
  lookup key. Logs written before this fix still load; the analyser recovers
  the collided pair by name.

### Added
- Dark and light themes with the Nextup Robotics logo (variant swaps to suit
  the background), brand-colored accents, and a header toggle.
- Hover crosshair on the **live** plot (previously analysis-only).
- Stats table in the analyser: min / max / mean / std dev / sample count.
- Export the plot as PNG, or the currently plotted series as CSV.
- Favourite objects (★) with a filter.
- More quick sets: Following error, Status + Mode.
- Backend probe on startup — reports master status or a clear reason.
- Settings persistence: theme, rate, output folder, joints, favourites, last
  object set, window geometry.
- Rate-ceiling estimate that warns when the target exceeds what SDO can give.
- Test suite (27 tests).

### Changed
- Split into `core/` (no Qt, testable headless) and `ui/`.
- Recordings default to a `csv/` folder, created automatically.
- Legends everywhere show the subindex (`[0x200B:01]`) so same-index objects
  are distinguishable.
