"""
NexScope entry point.
"""

from __future__ import annotations

import argparse
import os
import sys

from PyQt6 import QtWidgets

from . import __app_name__, __version__
from .core.model import load_presets
from .core.reader import make_reader
from .core.settings import Settings
from .ui.mainwindow import MainWindow
from .ui.resources import default_presets_path
from .ui.theme import THEMES, apply_theme


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="nexscope",
        description=f"{__app_name__} — EtherCAT SDO oscilloscope & logger "
                    f"(Nextup Robotics).",
    )
    p.add_argument("--presets", default=None,
                   help="Path to an SDO dictionary JSON (defaults to bundled).")
    p.add_argument("--simulate", action="store_true",
                   help="Synthetic data — run the UI with no EtherCAT master.")
    p.add_argument("--theme", choices=sorted(THEMES), default=None,
                   help="Override the saved theme for this run.")
    p.add_argument("--version", action="version",
                   version=f"{__app_name__} {__version__}")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    presets_path = args.presets or default_presets_path()
    if not os.path.exists(presets_path):
        print(f"ERROR: presets file not found: {presets_path}", file=sys.stderr)
        return 1
    try:
        presets = load_presets(presets_path)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: could not read presets: {e}", file=sys.stderr)
        return 1

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setOrganizationName("NextupRobotics")

    settings = Settings()
    if args.theme:
        settings.theme = args.theme
    apply_theme(app, THEMES[settings.theme])

    reader = make_reader(args.simulate)
    win = MainWindow(presets, reader, args.simulate, settings)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
