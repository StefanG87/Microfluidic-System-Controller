"""Balance readers and Ohaus/PuTTY log parsing."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Iterable, Protocol


OHAUS_DEFAULT_BAUDRATE = 9600
OHAUS_DEFAULT_TIMEOUT_S = 1.0


class BalanceReader(Protocol):
    def read_mass_g(self, timeout_s: float = 5.0) -> float:
        """Return the current mass in grams."""


@dataclass(frozen=True)
class BalanceSample:
    timestamp: datetime | None
    elapsed_s: float
    mass_g: float


class SerialBalance:
    """Serial reader for balances that stream ASCII mass values in grams.

    The default settings follow the Ohaus Adventurer Pro SOP: 9600 baud, 8N1,
    no flow control, unit g, and automatic print output at about 1 s intervals.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = OHAUS_DEFAULT_BAUDRATE,
        timeout_s: float = OHAUS_DEFAULT_TIMEOUT_S,
    ):
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("pyserial is required for live balance reading") from exc
        self.port = str(port)
        self.baudrate = int(baudrate)
        self.timeout_s = float(timeout_s)
        self._lock = Lock()
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=self.timeout_s,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

    def is_open(self) -> bool:
        """Return True while the serial port is open."""
        return bool(getattr(self._serial, "is_open", False))

    def close(self) -> None:
        """Close the serial connection if it is open."""
        try:
            self._serial.close()
        except Exception:
            pass

    def read_mass_g(self, timeout_s: float = 5.0) -> float:
        """Read one parseable mass value, waiting at most `timeout_s` seconds."""
        deadline = time.time() + max(0.0, float(timeout_s))
        with self._lock:
            while time.time() <= deadline:
                line = self._serial.readline().decode(errors="ignore").strip()
                mass = parse_mass_line(line)
                if mass is not None:
                    return mass
                if timeout_s <= 0:
                    break
        raise TimeoutError(f"No parseable balance mass received within {timeout_s:g} s")


def parse_mass_line(line: str) -> float | None:
    """Parse a balance line such as `12.345 g` or `ST,GS,+12.345 g`."""

    match = re.search(r"([-+]?\d+(?:[.,]\d+)?)\s*g\b", line, flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def parse_putty_ohaus_log(path: str | Path) -> list[BalanceSample]:
    """Parse the PuTTY/Ohaus log format used in the existing FlowByMass script."""

    path = Path(path)
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    if not lines:
        return []

    header_datetime: datetime | None = None
    header_match = re.search(r"PuTTY log (\d{4}\.\d{2}\.\d{2}) (\d{2}:\d{2}:\d{2})", lines[0])
    if header_match:
        header_datetime = datetime.strptime(
            f"{header_match.group(1)} {header_match.group(2)}",
            "%Y.%m.%d %H:%M:%S",
        )

    raw_pairs: list[tuple[datetime, float]] = []
    idx = 1 if header_match else 0
    while idx < len(lines):
        time_match = re.search(r"(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})", lines[idx])
        if not time_match:
            idx += 1
            continue
        timestamp = datetime.strptime(f"{time_match.group(1)} {time_match.group(2)}", "%d/%m/%y %H:%M:%S")
        mass = None
        for lookahead in range(idx + 1, min(idx + 4, len(lines))):
            mass = parse_mass_line(lines[lookahead])
            if mass is not None:
                idx = lookahead + 1
                break
        if mass is not None:
            raw_pairs.append((timestamp, mass))
        else:
            idx += 1

    if not raw_pairs:
        return []

    start_log_time = raw_pairs[0][0]
    out = []
    for timestamp, mass in raw_pairs:
        elapsed = (timestamp - start_log_time).total_seconds()
        real_timestamp = header_datetime + (timestamp - start_log_time) if header_datetime else timestamp
        out.append(BalanceSample(timestamp=real_timestamp, elapsed_s=float(elapsed), mass_g=float(mass)))
    return out


def flow_from_balance_samples(samples: Iterable[BalanceSample], density_g_cm3: float, window: int = 5) -> list[float]:
    """Return rolling gravimetric flow values in uL/min."""

    samples = list(samples)
    if window < 1:
        raise ValueError("window must be >= 1")
    density_g_ul = float(density_g_cm3) / 1000.0
    flows = [0.0 for _ in range(min(window, len(samples)))]
    for idx in range(window, len(samples)):
        prev = samples[idx - window]
        cur = samples[idx]
        dt = cur.elapsed_s - prev.elapsed_s
        if dt <= 0:
            flows.append(0.0)
            continue
        volume_ul = (cur.mass_g - prev.mass_g) / density_g_ul
        flows.append(float(volume_ul / (dt / 60.0)))
    return flows
