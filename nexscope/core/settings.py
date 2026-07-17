"""
Persistent user settings (theme, last rate, window geometry, favourites).

Stored via QSettings, so it lands in ~/.config/NextupRobotics/NexScope.conf
on Linux without us managing a file by hand.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import QSettings

ORG = "NextupRobotics"
APP = "NexScope"


class Settings:
    def __init__(self):
        self._s = QSettings(ORG, APP)

    # -- theme ------------------------------------------------------------ #
    @property
    def theme(self) -> str:
        return self._s.value("ui/theme", "dark", type=str)

    @theme.setter
    def theme(self, v: str):
        self._s.setValue("ui/theme", v)

    # -- recording defaults ----------------------------------------------- #
    @property
    def rate_hz(self) -> float:
        return self._s.value("record/rate_hz", 20.0, type=float)

    @rate_hz.setter
    def rate_hz(self, v: float):
        self._s.setValue("record/rate_hz", float(v))

    @property
    def out_dir(self) -> str:
        return self._s.value("record/out_dir", "csv", type=str)

    @out_dir.setter
    def out_dir(self, v: str):
        self._s.setValue("record/out_dir", v)

    @property
    def slaves(self) -> list[int]:
        raw = self._s.value("record/slaves", "", type=str)
        if not raw:
            return list(range(6))
        try:
            return [int(x) for x in raw.split(",") if x != ""]
        except ValueError:
            return list(range(6))

    @slaves.setter
    def slaves(self, v: list[int]):
        self._s.setValue("record/slaves", ",".join(str(x) for x in v))

    # -- favourites (object keys) ----------------------------------------- #
    @property
    def favourites(self) -> list[str]:
        raw = self._s.value("objects/favourites", "[]", type=str)
        try:
            out = json.loads(raw)
            return out if isinstance(out, list) else []
        except json.JSONDecodeError:
            return []

    @favourites.setter
    def favourites(self, v: list[str]):
        self._s.setValue("objects/favourites", json.dumps(v))

    # -- last selection --------------------------------------------------- #
    @property
    def last_objects(self) -> list[str]:
        raw = self._s.value("objects/last", "[]", type=str)
        try:
            out = json.loads(raw)
            return out if isinstance(out, list) else []
        except json.JSONDecodeError:
            return []

    @last_objects.setter
    def last_objects(self, v: list[str]):
        self._s.setValue("objects/last", json.dumps(v))

    # -- geometry --------------------------------------------------------- #
    def save_geometry(self, b: bytes):
        self._s.setValue("ui/geometry", b)

    def load_geometry(self):
        return self._s.value("ui/geometry")
