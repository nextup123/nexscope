"""
Core data model: SDO object definitions and preset loading.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# Integer types we can plot. Anything else (String) is logged but not graphed.
INT_TYPES = {"int8", "int16", "int32", "uint8", "uint16", "uint32"}

# Signed types, for range validation.
SIGNED_TYPES = {"int8", "int16", "int32"}

TYPE_RANGES = {
    "int8": (-128, 127),
    "uint8": (0, 255),
    "int16": (-32768, 32767),
    "uint16": (0, 65535),
    "int32": (-2147483648, 2147483647),
    "uint32": (0, 4294967295),
}


@dataclass(frozen=True)
class SdoObject:
    """A single entry from the presets JSON (e.g. 607Ah / 00h / int32)."""

    index: str  # "607Ah"
    subindex: str  # "00h"
    name: str  # "Target position"
    data_type: str  # "int32"

    # -- derived ---------------------------------------------------------- #
    @property
    def index_hex(self) -> str:
        """'607Ah' -> '0x607A'"""
        return "0x" + self.index.rstrip("hH").upper()

    @property
    def subindex_int(self) -> int:
        """'01h' -> 1"""
        return int(self.subindex.rstrip("hH"), 16)

    @property
    def is_numeric(self) -> bool:
        return self.data_type in INT_TYPES

    @property
    def key(self) -> str:
        """
        Unique id independent of slave.

        MUST include the subindex: 0x200B:1 (Motor speed actual value) and
        0x200B:2 (Speed reference) share an index and would otherwise collide.
        """
        return f"{self.index_hex}:{self.subindex_int}"

    @property
    def display(self) -> str:
        """'0x200B:01' — short, unambiguous, for legends and lists."""
        return f"{self.index_hex}:{self.subindex_int:02d}"

    @property
    def label(self) -> str:
        return f"{self.name}  [{self.display}]"

    def column_name(self, slave: int) -> str:
        """
        CSV column name for this object on a given slave.

        The subindex is encoded so same-index/different-subindex objects stay
        distinct: 's2_0x200Bsub01_Motor_speed_actual_value'
        """
        safe = self.name.replace(",", " ").replace(" ", "_")
        return f"s{slave}_{self.index_hex}sub{self.subindex_int:02d}_{safe}"

    def ethercat_args(self, slave: int) -> list[str]:
        """The argv for `ethercat upload` reading this object off `slave`."""
        return [
            "upload",
            self.index_hex,
            str(self.subindex_int),
            "--type",
            self.data_type,
            "-p",
            str(slave),
        ]


def load_presets(path: str) -> list[SdoObject]:
    """Load the SDO dictionary JSON into SdoObject instances."""
    with open(path) as f:
        raw = json.load(f)
    return [
        SdoObject(
            index=r["index"],
            subindex=r["subindex"],
            name=r["name"],
            data_type=r["data_type"],
        )
        for r in raw
    ]
