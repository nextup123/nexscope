"""
Resource path resolution — works when run from source or from an installed
package, and when frozen by PyInstaller.
"""

from __future__ import annotations

import os
import sys


def resource_dir() -> str:
    # PyInstaller unpacks to sys._MEIPASS
    base = getattr(sys, "_MEIPASS", None)
    if base:
        cand = os.path.join(base, "nexscope", "resources")
        if os.path.isdir(cand):
            return cand
        return os.path.join(base, "resources")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "resources")


def resource_path(name: str) -> str:
    return os.path.join(resource_dir(), name)


def logo_path(name: str) -> str:
    return resource_path(name)


def default_presets_path() -> str:
    return resource_path("sdo_presets.json")
