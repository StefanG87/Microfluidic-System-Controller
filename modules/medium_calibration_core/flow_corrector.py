"""Apply EtOH-dependent flow-sensor correction curves."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .paths import DEFAULT_CALIBRATION_DIR


class FlowCorrector:
    """Loads calibration JSON files and corrects sensor flow values."""

    def __init__(self, calibration_dir: str | Path = DEFAULT_CALIBRATION_DIR):
        self.calibration_dir = Path(calibration_dir)
        self.calibrations = self.load_calibrations()

    def load_calibrations(self) -> dict[float, dict[str, float]]:
        if not self.calibration_dir.exists():
            return {}
        result: dict[float, dict[str, float]] = {}
        for path in sorted(self.calibration_dir.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                etoh = float(data.get("etoh", data.get("etoh_percent")))
                slope = data.get("slope")
                intercept = data.get("intercept")
                if slope is None or intercept is None:
                    continue
                result[etoh] = {
                    "slope": float(slope),
                    "intercept": float(intercept),
                    "r2": float(data.get("r2", np.nan)),
                }
            except Exception:
                continue
        return result

    def params(self, etoh_percent: float) -> tuple[float, float, float]:
        if not self.calibrations:
            raise ValueError(f"No calibration JSON files found in {self.calibration_dir}")
        etohs = np.array(sorted(self.calibrations), dtype=float)
        etoh = float(etoh_percent)
        if etoh < etohs[0] or etoh > etohs[-1]:
            raise ValueError(f"EtOH {etoh:g}% outside calibration range {etohs[0]:g}..{etohs[-1]:g}%")
        slopes = np.array([self.calibrations[k]["slope"] for k in etohs], dtype=float)
        intercepts = np.array([self.calibrations[k]["intercept"] for k in etohs], dtype=float)
        r2s = np.array([self.calibrations[k]["r2"] for k in etohs], dtype=float)
        return (
            float(np.interp(etoh, etohs, slopes)),
            float(np.interp(etoh, etohs, intercepts)),
            float(np.interp(etoh, etohs, r2s)),
        )

    def correct_flow(self, sensor_flow_ul_min: float, etoh_percent: float) -> float:
        slope, intercept, _ = self.params(etoh_percent)
        return float(slope * float(sensor_flow_ul_min) + intercept)

    def correct_flow_verbose(self, sensor_flow_ul_min: float, etoh_percent: float) -> dict[str, Any]:
        slope, intercept, r2 = self.params(etoh_percent)
        corrected = slope * float(sensor_flow_ul_min) + intercept
        return {
            "sensor_flow_ul_min": float(sensor_flow_ul_min),
            "etoh_percent": float(etoh_percent),
            "slope": slope,
            "intercept": intercept,
            "r2": r2,
            "corrected_flow_ul_min": float(corrected),
        }
