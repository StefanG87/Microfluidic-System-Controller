"""Sampling control card for the v3 GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QSpinBox

from ui_v3.fluent_compat import CardWidget, PrimaryPushButton, PushButton, add_info_header, make_card_layout, mark_primary_action, stretch_row


class SamplingCard(CardWidget):
    """Configure sampling interval and measurement state."""

    def __init__(self, controller, parent=None, show_interval: bool = True):
        super().__init__(parent)
        self.controller = controller
        self.show_interval = bool(show_interval)
        layout = make_card_layout(self)
        add_info_header(
            layout,
            "Recording",
            "New Measurement clears the current buffers and restarts the plot timebase. "
            "Live monitoring continues after hardware connection, so CSV export can also use buffered samples without an explicit measurement run.",
        )

        self.interval = None
        if self.show_interval:
            self.interval = QSpinBox()
            self.interval.setRange(1, 600000)
            self.interval.setValue(controller.sampling_interval_ms)
            self.interval.setSuffix(" ms")
            self.interval.valueChanged.connect(controller.set_sampling_interval_ms)

        self.start_button = mark_primary_action(PrimaryPushButton("Refresh Plot"))
        self.stop_button = PushButton("Stop + Export")
        self.export_button = PushButton("Export CSV")
        self.start_button.clicked.connect(lambda _checked=False: self._refresh_plot())
        self.stop_button.clicked.connect(lambda _checked=False: self._stop_measurement())
        self.export_button.clicked.connect(lambda _checked=False: self._export_csv())

        if self.interval is not None:
            layout.addWidget(self.interval)
        layout.addWidget(stretch_row(self.start_button, self.stop_button, self.export_button))
        controller.status_changed.connect(self._apply_status)
        controller.sample_ready.connect(lambda _sample: self._apply_status(controller.status_snapshot()))
        self._apply_status(controller.status_snapshot())

    def _apply_status(self, status: dict) -> None:
        """Keep interval and button state aligned with runtime state."""
        if self.interval is not None:
            self.interval.blockSignals(True)
            self.interval.setValue(int(status.get("sampling_interval_ms", self.interval.value()) or 1))
            self.interval.blockSignals(False)
        measuring = bool(status.get("measuring"))
        connected = bool(status.get("connected"))
        self.start_button.setEnabled(connected)
        self.stop_button.setEnabled(measuring)
        self.export_button.setEnabled(self.controller.measurement_has_data())
        if self.interval is not None:
            self.interval.setEnabled(not measuring)

    def _refresh_plot(self) -> None:
        """Clear current buffers and restart the plot timebase after user confirmation."""
        if self.controller.measurement_has_data():
            answer = QMessageBox.question(
                self,
                "Refresh Plot",
                "Refreshing the plot clears the current buffered data for plotting and CSV export.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.controller.start_measurement()

    def _export_csv(self) -> None:
        """Export any currently buffered live samples without requiring a started run."""
        if not self.controller.measurement_has_data():
            self.controller.append_log("[v3] CSV export skipped: no samples available yet.")
            return
        default_path = self.controller.suggest_csv_path()
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export Measurement CSV",
            default_path,
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return
        if Path(path).suffix.lower() != ".csv":
            path = f"{path}.csv"
        try:
            self.controller.export_csv(path)
        except Exception as exc:
            self.controller.append_log(f"[v3] CSV export failed: {exc}")

    def _stop_measurement(self) -> None:
        """Stop a manual measurement and offer the same explicit export workflow as classic v2."""
        self.controller.stop_measurement()
        if not self.controller.measurement_has_data():
            self.controller.append_log("[v3] Measurement stopped without samples; CSV export skipped.")
            return

        default_path = self.controller.suggest_csv_path()
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export Measurement CSV",
            default_path,
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            self.controller.append_log("[v3] Manual measurement stopped; CSV export skipped by user.")
            return
        if Path(path).suffix.lower() != ".csv":
            path = f"{path}.csv"
        try:
            self.controller.export_csv(path)
        except Exception as exc:
            self.controller.append_log(f"[v3] CSV export after stop failed: {exc}")
