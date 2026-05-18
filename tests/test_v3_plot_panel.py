"""Smoke tests for v3 plot-panel interaction helpers."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui_v3.plot_panel import PLOT_REDRAW_INTERVAL_MS
from ui_v3.plot_panel import PlotPanel


class V3PlotPanelTests(unittest.TestCase):
    """Verify plot helpers that keep live plotting usable during interaction."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.load_settings_patch = patch("ui_v3.plot_panel.load_plot_settings", return_value={})
        self.load_settings_patch.start()
        self.panel = PlotPanel()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.load_settings_patch.stop()

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

    def test_channel_presets_update_expected_checkboxes(self):
        with patch("ui_v3.plot_panel.save_plot_settings", return_value=True):
            self.panel.apply_channel_preset("clear")
            self.assertEqual(self._checked_labels(), [])

            self.panel.apply_channel_preset("pressure")
            self.assertEqual(self._checked_labels(), ["Target", "Corrected", "Measured"])

            self.panel.apply_channel_preset("sensors")
            checked = self._checked_labels()
            self.assertIn("Corrected", checked)
            self.assertIn("Flow 1", checked)
            self.assertNotIn("Rotary", checked)

            self.panel.apply_channel_preset("all")
            self.assertEqual(set(self._checked_labels()), set(self.panel.checkboxes))

    def test_visible_channels_create_figure_legend(self):
        if self.panel._figure is None:
            self.skipTest("Matplotlib Qt canvas is not available")

        sample = SimpleNamespace(
            rel_time=0.0,
            corrected_pressure=1.2,
            measured_pressure=1.4,
            rotary_active=0,
            valve_states=[],
            flow_values=[],
            fluigent_values=[],
            extra_values=[],
        )

        with patch("ui_v3.plot_panel.save_plot_settings", return_value=True):
            self.panel.apply_channel_preset("pressure")
            self.panel.update_target(10.0)
            self.panel.append_sample(sample)
            self.panel.update_plot()

        self.assertTrue(self.panel._figure.legends)
        legend_labels = [
            text.get_text()
            for legend in self.panel._figure.legends
            for text in legend.get_texts()
        ]
        self.assertIn("Corrected", legend_labels)

    def test_axis_scale_settings_apply_and_persist(self):
        if self.panel._axis is None:
            self.skipTest("Matplotlib Qt canvas is not available")

        with patch("ui_v3.plot_panel.save_plot_settings", return_value=True) as save_mock:
            self.panel.set_axis_scale("pressure", "log")
            self.panel.set_axis_scale("flow", "log")
            self.panel.set_axis_scale("time", "log")

        self.assertEqual(self.panel.axis_scale("pressure"), "log")
        self.assertEqual(self.panel.axis_scale("flow"), "log")
        self.assertEqual(self.panel.axis_scale("time"), "log")
        self.assertEqual(self.panel._axis.get_yscale(), "log")
        self.assertEqual(self.panel._flow_axis.get_yscale(), "log")
        self.assertEqual(self.panel._axis.get_xscale(), "log")
        self.assertTrue(save_mock.called)

    def test_live_redraw_timer_is_throttled(self):
        self.assertEqual(self.panel._plot_update_timer.interval(), PLOT_REDRAW_INTERVAL_MS)
        self.assertGreaterEqual(PLOT_REDRAW_INTERVAL_MS, 250)

    def _checked_labels(self) -> list[str]:
        """Return checked plot-channel labels in display order."""
        return [
            label
            for label, checkbox in self.panel.checkboxes.items()
            if checkbox.isChecked()
        ]


if __name__ == "__main__":
    unittest.main()
