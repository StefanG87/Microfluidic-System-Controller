"""Live sensor overview card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ui_v3.fluent_compat import CardWidget, CaptionLabel, add_info_header, make_card_layout


class SensorCard(CardWidget):
    """Display the latest sampled values from pressure and cataloged sensors."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._value_labels = {}
        self._title_labels = {}
        self._sensor_order = []
        self._sensor_units = {}
        self._current_column_count = 0
        layout = make_card_layout(self)
        add_info_header(
            layout,
            "Live Sensors",
            "Shows the latest sampled values from the runtime device catalog. "
            "Rows are rebuilt after hardware refresh so pressure, flow, Fluigent, and future generic sensors stay aligned with CSV export.",
        )

        self.status = CaptionLabel("No sample yet.")
        layout.addWidget(self.status)

        self.table = QWidget()
        self.grid = QGridLayout(self.table)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(2)
        layout.addWidget(self.table)

        self._rebuild_sensor_rows(controller.device_catalog.to_embedded_editor_info())
        controller.device_catalog_changed.connect(self._rebuild_sensor_rows)
        controller.status_changed.connect(self._apply_status)
        controller.sample_ready.connect(self._apply_sample)
        controller.sample_failed.connect(self._apply_sample_failed)
        self._apply_status(controller.status_snapshot())

    def _set_value(self, name: str, value: str, unit: str = "") -> None:
        """Create or update one labeled sensor value row."""
        if name not in self._value_labels:
            title = CaptionLabel(name)
            title.setObjectName("V3MetricCaption")
            value_label = QLabel()
            value_label.setObjectName("V3MetricValue")
            self._title_labels[name] = title
            self._value_labels[name] = value_label
            self._sensor_order.append(name)
            self._layout_sensor_rows()
        value_text = str(value)
        unit_text = str(unit or "").strip()
        self._value_labels[name].setText(f"{value_text} {unit_text}".strip())

    def _clear_rows(self) -> None:
        """Remove all rows before rebuilding the sensor list."""
        self._remove_grid_items(delete_widgets=True)
        self._value_labels.clear()
        self._title_labels.clear()
        self._sensor_order.clear()
        self._current_column_count = 0

    def _remove_grid_items(self, delete_widgets: bool = False) -> None:
        """Remove widgets from the grid, optionally deleting them during catalog rebuilds."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self.grid.removeWidget(widget)
                if delete_widgets:
                    widget.deleteLater()

    def _desired_column_count(self) -> int:
        """Choose a readable number of sensor columns for the available width."""
        width = max(self.table.width(), self.width())
        if width >= 620:
            return 3
        if width >= 340:
            return 2
        return 1

    def _layout_sensor_rows(self) -> None:
        """Reflow sensor rows when the panel is resized."""
        if not self._sensor_order:
            return
        columns = self._desired_column_count()
        self._current_column_count = columns
        self._remove_grid_items(delete_widgets=False)
        for index, name in enumerate(self._sensor_order):
            title = self._title_labels.get(name)
            value_label = self._value_labels.get(name)
            if title is None or value_label is None:
                continue
            row = index // columns
            column = (index % columns) * 2
            self.grid.addWidget(title, row, column)
            self.grid.addWidget(value_label, row, column + 1)
            self.grid.setColumnStretch(column, 0)
            self.grid.setColumnStretch(column + 1, 1)

    def resizeEvent(self, event) -> None:
        """Keep the live-sensor grid readable as the dashboard width changes."""
        super().resizeEvent(event)
        columns = self._desired_column_count()
        if columns != self._current_column_count:
            QTimer.singleShot(0, self._layout_sensor_rows)

    def _rebuild_sensor_rows(self, catalog_info: dict) -> None:
        """Show all cataloged sensors immediately after hardware discovery."""
        self._clear_rows()
        self._sensor_units = {}

        descriptors = list(catalog_info.get("sensor_descriptors", []))
        if not descriptors:
            self._set_value("Sensors", "not connected", "")
            return

        for descriptor in descriptors:
            name = str(descriptor.get("name", "")).strip()
            if not name:
                continue
            unit = str(descriptor.get("unit", "") or "")
            self._sensor_units[name] = unit
            self._set_value(name, "--", unit)

    def _apply_status(self, status: dict) -> None:
        """Update status-derived values that do not require a fresh sample."""
        if not bool(status.get("connected")):
            self.status.setText("Disconnected")

    def _apply_sample(self, sample) -> None:
        """Update the card with the latest sampled values."""
        self.status.setText(f"Last sample: {float(sample.rel_time):.2f} s")
        self._set_value("Internal", f"{float(sample.measured_pressure):.2f}", "mbar")
        for name, value in sample.flow_values:
            self._set_value(name, self._format_number(value), self._sensor_units.get(name, "uL/min"))
        for name, value in sample.fluigent_values:
            self._set_value(name, self._format_number(value), self._sensor_units.get(name, "mbar"))
        for name, value, unit in sample.extra_values:
            self._set_value(name, self._format_number(value), unit)

    def _apply_sample_failed(self, message: str) -> None:
        """Show timer-driven sampling failures next to the sensor table."""
        self.status.setText(str(message).replace("[v3] ", ""))

    @staticmethod
    def _format_number(value) -> str:
        """Format numeric sensor values without hiding non-numeric telemetry."""
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return "--" if value is None else str(value)
