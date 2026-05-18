"""Tests for v3 live-sensor card filtering."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from modules.device_catalog import (
    SENSOR_KIND_FLOW,
    SENSOR_KIND_FLUIGENT_PRESSURE,
    SENSOR_KIND_INTERNAL_PRESSURE,
    SENSOR_KIND_WEIGHT,
    UNIT_FLOW_UL_MIN,
    UNIT_PRESSURE_MBAR,
    UNIT_WEIGHT_G,
    DeviceCatalog,
)
from ui_v3.cards.sensor_card import SensorCard


class _FakeController(QObject):
    """Minimal controller shape required by SensorCard."""

    device_catalog_changed = Signal(object)
    status_changed = Signal(object)
    sample_ready = Signal(object)
    sample_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.device_catalog = DeviceCatalog()
        self.device_catalog.register_sensor("Internal", SENSOR_KIND_INTERNAL_PRESSURE, UNIT_PRESSURE_MBAR)
        self.device_catalog.register_sensor("Flow 1", SENSOR_KIND_FLOW, UNIT_FLOW_UL_MIN)
        self.device_catalog.register_sensor("SN100", SENSOR_KIND_FLUIGENT_PRESSURE, UNIT_PRESSURE_MBAR)
        self.device_catalog.register_sensor("Balance", SENSOR_KIND_WEIGHT, UNIT_WEIGHT_G)

    def status_snapshot(self):
        """Return a connected status snapshot for widget initialization."""
        return {"connected": True}


class V3SensorCardTests(unittest.TestCase):
    """Verify pressure-only sensor cards remain pressure-only."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        if hasattr(self, "card"):
            self.card.close()
            self.card.deleteLater()

    def test_pressure_filter_shows_only_internal_and_fluigent_pressure(self):
        controller = _FakeController()

        self.card = SensorCard(
            controller,
            sensor_kinds={SENSOR_KIND_INTERNAL_PRESSURE, SENSOR_KIND_FLUIGENT_PRESSURE},
        )

        self.assertEqual(self.card._sensor_order, ["Internal", "SN100"])

        sample = SimpleNamespace(
            rel_time=1.0,
            measured_pressure=12.34,
            flow_values=[("Flow 1", 5.0)],
            fluigent_values=[("SN100", 2.5)],
            extra_values=[("Balance", 1.23, "g")],
        )
        self.card._apply_sample(sample)

        self.assertIn("12.34", self.card._value_labels["Internal"].text())
        self.assertIn("2.500", self.card._value_labels["SN100"].text())
        self.assertNotIn("Flow 1", self.card._value_labels)
        self.assertNotIn("Balance", self.card._value_labels)


if __name__ == "__main__":
    unittest.main()
