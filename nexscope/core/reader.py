"""
SDO reading backends.

Real backend shells out to the IgH `ethercat` CLI:
    ethercat upload 0x607A 0 --type int32 -p 3
    -> "0x000539f4 342516"      (hex, decimal)

We take the decimal (last field), which is already correctly signed.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import time

from .model import SdoObject

ETHERCAT_BIN = "ethercat"


class SdoReadError(Exception):
    pass


class BaseReader:
    """Interface for SDO readers."""

    def read(self, obj: SdoObject, slave: int) -> float | None:
        raise NotImplementedError

    def probe(self) -> tuple[bool, str]:
        """Return (ok, message) describing backend availability."""
        raise NotImplementedError


class EthercatReader(BaseReader):
    """Reads SDOs by invoking the `ethercat` command-line tool."""

    def __init__(self, timeout: float = 1.0):
        self.timeout = timeout
        self.last_error: str | None = None

    def probe(self) -> tuple[bool, str]:
        if shutil.which(ETHERCAT_BIN) is None:
            return False, (
                f"'{ETHERCAT_BIN}' not found on PATH. Is the IgH master "
                f"installed? Use Simulation mode to test the UI."
            )
        try:
            out = subprocess.run(
                [ETHERCAT_BIN, "slaves"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            return False, f"ethercat present but not responding: {e}"
        if out.returncode != 0:
            err = (out.stderr or "").strip()
            return False, f"`ethercat slaves` failed: {err}"
        n = len([l for l in out.stdout.splitlines() if l.strip()])
        return True, f"EtherCAT master OK — {n} slave(s) online."

    def read(self, obj: SdoObject, slave: int) -> float | None:
        cmd = [ETHERCAT_BIN] + obj.ethercat_args(slave)
        try:
            out = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )
        except subprocess.TimeoutExpired:
            self.last_error = f"timeout reading {obj.display} on slave {slave}"
            return None
        except OSError as e:
            self.last_error = str(e)
            return None

        if out.returncode != 0:
            self.last_error = (out.stderr or "").strip() or "non-zero exit"
            return None

        text = out.stdout.strip()
        if not text:
            self.last_error = "empty response"
            return None

        # "0x000539f4 342516" -> take decimal (last field)
        last = text.split()[-1]
        try:
            return float(int(last))
        except ValueError:
            pass
        try:
            return float(last)
        except ValueError:
            self.last_error = f"unparseable response: {text!r}"
            return None


class SimulatedReader(BaseReader):
    """
    Generates plausible motion so the UI can be exercised without hardware.

    Each joint gets a sine at a different frequency/phase; each distinct object
    is offset so overlapping curves stay visually separable.
    """

    def __init__(self):
        self._t0 = time.time()

    def probe(self) -> tuple[bool, str]:
        return True, "Simulation mode — synthetic data, no hardware."

    def read(self, obj: SdoObject, slave: int) -> float | None:
        t = time.time() - self._t0
        freq = 0.2 + 0.1 * slave
        phase = slave * math.pi / 3
        base = 100000 * math.sin(2 * math.pi * freq * t + phase)
        offset = (hash(obj.key) % 7) * 5000
        noise = (hash((int(t * 1000), slave, obj.key)) % 1000) - 500
        return base + offset + noise


def make_reader(simulate: bool) -> BaseReader:
    return SimulatedReader() if simulate else EthercatReader()
