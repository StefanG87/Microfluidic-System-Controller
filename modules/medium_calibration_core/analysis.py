"""Calibration analysis and export."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .models import CalibrationSession, MeasurementRecord
from .paths import DEFAULT_CALIBRATION_DIR


@dataclass(frozen=True)
class LinearFit:
    slope: float
    intercept: float
    r2: float


class CalibrationAnalyzer:
    """Computes repeat statistics and sensor-to-gravimetric calibration fits."""

    def __init__(self, session: CalibrationSession):
        self.session = session

    @property
    def density_g_per_ul(self) -> float:
        return self.session.density_g_cm3 / 1000.0

    def grav_flow_ul_min(self, record: MeasurementRecord) -> float | None:
        delta_mass = record.delta_mass_g
        duration_s = record.measured_duration_s or self.session.measurement_duration_s
        if delta_mass is None or duration_s <= 0 or self.density_g_per_ul <= 0:
            return None
        volume_ul = delta_mass / self.density_g_per_ul
        return float(volume_ul / (duration_s / 60.0))

    def repeat_rows(self) -> list[dict[str, Any]]:
        rows = []
        for record in self.session.records:
            grav = self.grav_flow_ul_min(record)
            rows.append(
                {
                    "target_pressure_mbar": float(record.target_pressure_mbar),
                    "repeat_index": int(record.repeat_index),
                    "pressure_mean_mbar": record.pressure_mean(),
                    "pressure_std_mbar": record.pressure_std(),
                    "sensor_mean_ul_min": record.sensor_mean(),
                    "sensor_std_ul_min": record.sensor_std(),
                    "sensor_volume_ul": record.sensor_integrated_volume_ul(),
                    "mass_start_g": record.mass_start_g,
                    "mass_end_g": record.mass_end_g,
                    "delta_mass_g": record.delta_mass_g,
                    "duration_s": record.measured_duration_s,
                    "grav_flow_ul_min": grav,
                }
            )
        return rows

    def pressure_summary(self) -> list[dict[str, Any]]:
        out = []
        for pressure, records in sorted(self.session.records_by_pressure().items()):
            sensor_vals = np.array([r.sensor_mean() for r in records], dtype=float)
            grav_vals = np.array(
                [v for v in (self.grav_flow_ul_min(r) for r in records) if v is not None],
                dtype=float,
            )
            pressure_vals = np.array([r.pressure_mean() for r in records], dtype=float)
            out.append(
                {
                    "target_pressure_mbar": pressure,
                    "n_repeats": len(records),
                    "pressure_mean_mbar": float(np.mean(pressure_vals)) if pressure_vals.size else pressure,
                    "pressure_std_mbar": float(np.std(pressure_vals)) if pressure_vals.size else 0.0,
                    "sensor_mean_ul_min": float(np.mean(sensor_vals)) if sensor_vals.size else 0.0,
                    "sensor_std_ul_min": float(np.std(sensor_vals)) if sensor_vals.size else 0.0,
                    "grav_mean_ul_min": float(np.mean(grav_vals)) if grav_vals.size else None,
                    "grav_std_ul_min": float(np.std(grav_vals)) if grav_vals.size else None,
                }
            )
        return out

    def fit(self) -> LinearFit | None:
        rows = [r for r in self.repeat_rows() if r["grav_flow_ul_min"] is not None]
        if len(rows) < 2:
            return None
        x = np.array([r["sensor_mean_ul_min"] for r in rows], dtype=float)
        y = np.array([r["grav_flow_ul_min"] for r in rows], dtype=float)
        if np.allclose(x, x[0]):
            return None
        slope, intercept = np.polyfit(x, y, 1)
        y_hat = slope * x + intercept
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 if ss_tot == 0.0 else 1.0 - ss_res / ss_tot
        return LinearFit(float(slope), float(intercept), float(r2))

    def export_payload(self) -> dict[str, Any]:
        fit = self.fit()
        return {
            "schema_version": 2,
            "medium": "EtOH",
            "etoh": float(self.session.etoh_percent),
            "fit_model": "linear_sensor_to_gravimetric",
            "slope": fit.slope if fit else None,
            "intercept": fit.intercept if fit else None,
            "r2": fit.r2 if fit else None,
            "meta": {
                "density_g_per_cm3": float(self.session.density_g_cm3),
                "duration_s": float(self.session.measurement_duration_s),
                "warmup_cut_s": float(self.session.warmup_cut_s),
                "created_at": self.session.created_at,
                **self.session.metadata,
            },
            "pressure_dependence": self.pressure_summary(),
            "repeats": self.repeat_rows(),
            "raw_session": self.session.to_jsonable(),
        }

    def save(self, folder: str | Path = DEFAULT_CALIBRATION_DIR) -> Path:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        etoh_tag = f"{self.session.etoh_percent:.1f}".replace(".", "_")
        path = folder / f"calibration_EtOH_{etoh_tag}pct.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.export_payload(), fh, indent=2)
        return path
