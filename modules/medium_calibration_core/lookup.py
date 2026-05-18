"""Lookup-table access for density and pressure-offset data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from .paths import DEFAULT_DENSITY_LOOKUP, DEFAULT_PRESSURE_OFFSET


@dataclass(frozen=True)
class DensityLookup:
    """Interpolates EtOH density values from a JSON lookup table.

    The stored values are expected in g/cm3 and keys are EtOH percentages.
    """

    values: Mapping[float, float]
    source: Path | None = None

    @classmethod
    def load(cls, path: str | Path = DEFAULT_DENSITY_LOOKUP) -> "DensityLookup":
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        values = {float(k): float(v) for k, v in raw.items()}
        if not values:
            raise ValueError(f"Density lookup is empty: {path}")
        return cls(values=values, source=path)

    def density(self, etoh_percent: float) -> float:
        keys = np.array(sorted(self.values), dtype=float)
        vals = np.array([self.values[k] for k in keys], dtype=float)
        etoh = float(etoh_percent)
        if etoh < keys[0] or etoh > keys[-1]:
            raise ValueError(
                f"EtOH {etoh:g}% is outside lookup range "
                f"{keys[0]:g}..{keys[-1]:g}%"
            )
        return float(np.interp(etoh, keys, vals))


@dataclass
class PressureOffsetStore:
    """Reads and writes the shared pressure-offset JSON format."""

    path: Path = DEFAULT_PRESSURE_OFFSET

    def load(self, default: float = 0.0) -> float:
        if not self.path.exists():
            return float(default)
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return float(data.get("offset", default))
        except Exception:
            return float(default)

    def save(self, offset_mbar: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump({"offset": float(offset_mbar)}, fh, indent=2)
