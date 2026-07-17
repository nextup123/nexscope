"""
NexScope entry point.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys

from PyQt6 import QtCore, QtWidgets

from . import __app_name__, __version__
from .core.model import load_presets
from .core.reader import make_reader
from .core.settings import Settings
from .ui.mainwindow import MainWindow
from .ui.resources import default_presets_path
from .ui.theme import THEMES, apply_theme


def install_sigint_handler(app: QtWidgets.QApplication, win: QtWidgets.QMainWindow):
    """
    Make Ctrl+C in the terminal quit the app.

    Qt's event loop is C++ and never yields to the interpreter, so a plain
    signal.signal() handler would only fire once some Python happens to run —
    which, while idle in exec(), is never. The idle QTimer below forces the
    interpreter to wake periodically so pending signals get delivered.

    We route through win.close() rather than app.quit() so the normal
    closeEvent runs: the recorder thread is stopped and settings are saved,
    exactly as if the window's X button was clicked.
    """

    def handler(_signum, _frame):
        print("\nInterrupt — shutting down NexScope…")
        win.close()
        app.quit()

    signal.signal(signal.SIGINT, handler)
    try:
        signal.signal(signal.SIGTERM, handler)
    except (ValueError, OSError):
        pass  # not always available off the main thread

    timer = QtCore.QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)  # yield to Python so signals land
    return timer


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

    # keep a reference so the timer isn't garbage collected
    _sigint_timer = install_sigint_handler(app, win)  # noqa: F841

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())