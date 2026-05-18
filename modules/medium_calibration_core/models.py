"""Data models for calibration measurements and exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MeasurementSample:
    """One time-aligned sample from a calibration repeat."""

    t_s: float
    flow_ul_min: float
    pressure_mbar: float
    mass_g: float | None = None


@dataclass
class MeasurementRecord:
    """One repeat at one target pressure."""

    target_pressure_mbar: float
    samples: list[MeasurementSample]
    repeat_index: int = 0
    mass_start_g: float | None = None
    mass_end_g: float | None = None
    duration_s: float | None = None
    notes: str = ""

    @property
    def measured_duration_s(self) -> float:
        if self.duration_s is not None:
            return float(self.duration_s)
        if len(self.samples) < 2:
            return 0.0
        return float(max(s.t_s for s in self.samples) - min(s.t_s for s in self.samples))

    @property
    def delta_mass_g(self) -> float | None:
        if self.mass_start_g is None or self.mass_end_g is None:
            return None
        return float(self.mass_end_g - self.mass_start_g)

    def sensor_mean(self) -> float:
        vals = [s.flow_ul_min for s in self.samples]
        return float(np.mean(vals)) if vals else 0.0

    def sensor_std(self) -> float:
        vals = [s.flow_ul_min for s in self.samples]
        return float(np.std(vals)) if vals else 0.0

    def pressure_mean(self) -> float:
        vals = [s.pressure_mbar for s in self.samples]
        return float(np.mean(vals)) if vals else float(self.target_pressure_mbar)

    def pressure_std(self) -> float:
        vals = [s.pressure_mbar for s in self.samples]
        return float(np.std(vals)) if vals else 0.0

    def sensor_integrated_volume_ul(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        times = np.array([s.t_s for s in self.samples], dtype=float)
        flows = np.array([s.flow_ul_min for s in self.samples], dtype=float)
        return float(np.trapz(flows / 60.0, times))


@dataclass
class CalibrationSession:
    """A complete EtOH calibration session."""

    etoh_percent: float
    density_g_cm3: float
    measurement_duration_s: float
    warmup_cut_s: float = 0.7
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    records: list[MeasurementRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_record(self, record: MeasurementRecord) -> None:
        self.records.append(record)

    def records_by_pressure(self) -> dict[float, list[MeasurementRecord]]:
        grouped: dict[float, list[MeasurementRecord]] = {}
        for record in self.records:
            grouped.setdefault(float(record.target_pressure_mbar), []).append(record)
        return grouped

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "etoh_percent": self.etoh_percent,
            "density_g_cm3": self.density_g_cm3,
            "measurement_duration_s": self.measurement_duration_s,
            "warmup_cut_s": self.warmup_cut_s,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "records": [
                {
                    "target_pressure_mbar": r.target_pressure_mbar,
                    "repeat_index": r.repeat_index,
                    "mass_start_g": r.mass_start_g,
                    "mass_end_g": r.mass_end_g,
                    "delta_mass_g": r.delta_mass_g,
                    "duration_s": r.measured_duration_s,
                    "notes": r.notes,
                    "samples": [s.__dict__ for s in r.samples],
                }
                for r in self.records
            ],
        }
