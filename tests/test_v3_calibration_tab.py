"""Smoke tests for the v3 calibration page."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui_v3.calibration_tab import MediumCalibrationTab, hardware_context_from_controller


class V3CalibrationTabTests(unittest.TestCase):
    """Verify that the PySide6 calibration tab is importable and context-driven."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        if hasattr(self, "tab"):
            self.tab.close()
            self.tab.deleteLater()

    def test_tab_starts_without_hardware_context(self):
        self.tab = MediumCalibrationTab(hardware=None)

        self.assertFalse(self.tab.start_button.isEnabled())
        self.assertIn("No connected hardware", self.tab.context_label.text())

    def test_hardware_context_uses_internal_pressure_when_no_fluigent_sensor_exists(self):
        controller = _fake_controller()

        context = hardware_context_from_controller(controller)

        self.assertEqual(len(context.pressure_sensors), 1)
        self.assertAlmostEqual(context.pressure_sensors[0].read_pressure(), 100.0)
        self.assertEqual(context.valve_labels, ["Valve 1", "Valve 5"])

    def test_tab_populates_hardware_choices(self):
        self.tab = MediumCalibrationTab(hardware=hardware_context_from_controller(_fake_controller()))

        self.assertTrue(self.tab.start_button.isEnabled())
        self.assertEqual(self.tab.flow_combo.currentText(), "Flow 1")
        self.assertEqual(self.tab.pressure_combo.currentText(), "Internal")
        self.assertEqual(self.tab.pneumatic_combo.currentText(), "Valve 1")
        self.assertEqual(self.tab.fluidic_combo.currentText(), "Valve 5")


def _fake_controller():
    """Return a minimal controller-shaped object for calibration context tests."""
    return SimpleNamespace(
        pressure_source=object(),
        valves=[object(), object()],
        flow_sensors=[SimpleNamespace(name="Flow 1")],
        fluigent_sensors=[],
        offset=16.3,
        balance_reader=None,
        balance_port="COM9",
        _valve_meta=[
            {"button_label": "Valve 1", "editor_name": "Pneumatic: 1", "group": "pneumatic"},
            {"button_label": "Valve 5", "editor_name": "Fluidic: 5", "group": "fluidic"},
        ],
        append_log=lambda message: None,
        read_internal_pressure_mbar=lambda: 116.3,
    )


if __name__ == "__main__":
    unittest.main()
