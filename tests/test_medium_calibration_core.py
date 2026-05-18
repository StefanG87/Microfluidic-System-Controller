"""Smoke tests for the medium calibration core."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.medium_calibration_core.analysis import CalibrationAnalyzer
from modules.medium_calibration_core.lookup import DensityLookup
from modules.medium_calibration_core.models import CalibrationSession, MeasurementRecord, MeasurementSample


class MediumCalibrationCoreTests(unittest.TestCase):
    """Verify that the copied calibration core is usable inside the MF repo."""

    def test_density_lookup_loads_repo_resource(self):
        lookup = DensityLookup.load()

        self.assertGreater(lookup.density(0.0), lookup.density(100.0))
        self.assertGreater(lookup.density(50.0), 0.7)

    def test_calibration_analyzer_saves_linear_fit_payload(self):
        session = CalibrationSession(
            etoh_percent=50.0,
            density_g_cm3=0.9,
            measurement_duration_s=60.0,
            warmup_cut_s=0.0,
        )
        session.add_record(
            MeasurementRecord(
                target_pressure_mbar=50.0,
                repeat_index=1,
                samples=[MeasurementSample(t_s=0.0, flow_ul_min=100.0, pressure_mbar=50.0)],
                mass_start_g=0.0,
                mass_end_g=0.9,
                duration_s=60.0,
            )
        )
        session.add_record(
            MeasurementRecord(
                target_pressure_mbar=100.0,
                repeat_index=1,
                samples=[MeasurementSample(t_s=0.0, flow_ul_min=200.0, pressure_mbar=100.0)],
                mass_start_g=0.0,
                mass_end_g=1.8,
                duration_s=60.0,
            )
        )

        analyzer = CalibrationAnalyzer(session)
        fit = analyzer.fit()

        self.assertIsNotNone(fit)
        with tempfile.TemporaryDirectory() as tmpdir:
            saved = analyzer.save(Path(tmpdir))
            self.assertTrue(saved.exists())


if __name__ == "__main__":
    unittest.main()
