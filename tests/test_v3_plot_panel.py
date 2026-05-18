"""Smoke tests for v3 plot-panel interaction helpers."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui_v3.plot_panel import PlotPanel


class V3PlotPanelTests(unittest.TestCase):
    """Verify plot helpers that keep live plotting usable during interaction."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.panel = PlotPanel()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()

    def test_log_y_limits_ignore_nonpositive_values(self):
        if self.panel._axis is None:
            self.skipTest("Matplotlib Qt canvas is not available")

        self.panel._axis.set_yscale("log")
        self.panel._set_axis_y_limits(self.panel._axis, [-1.0, 0.0, 2.0, 5.0])

        y_min, y_max = self.panel._axis.get_ylim()
        self.assertGreater(y_min, 0.0)
        self.assertGreater(y_max, y_min)

    def test_autoscale_button_clears_manual_view(self):
        self.panel._manual_view_limits = {"pressure": ((1.0, 2.0), (0.0, 1.0))}
        if self.panel.lock_view_button is not None:
            self.panel.lock_view_button.setChecked(True)

        self.panel._reset_manual_view()

        self.assertIsNone(self.panel._manual_view_limits)
        if self.panel.lock_view_button is not None:
            self.assertFalse(self.panel.lock_view_button.isChecked())


if __name__ == "__main__":
    unittest.main()
