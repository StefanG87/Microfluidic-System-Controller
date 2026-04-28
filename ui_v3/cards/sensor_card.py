"""Live sensor overview card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ui_v3.fluent_compat import BodyLabel, CardWidget, CaptionLabel, PushButton, make_card_layout


class SensorCard(CardWidget):
    """Display the latest sampled values from pressure and cataloged sensors."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._value_labels = {}
        layout = make_card_layout(self)
        layout.addWidget(BodyLabel("Live Sensors"))
        layout.addWidget(CaptionLabel("Shows the latest measurement tick; use sampling or Sample Once to update."))

        self.sample_button = PushButton("Sample Once")
        self.sample_button.clicked.connect(lambda _checked=False: controller.sample_once())
        layout.addWidget(self.sample_button)

        self.table = QWidget()
        self.grid = QGridLayout(self.table)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(8)
        layout.addWidget(self.table)

        self._set_value("Measured Pressure", "--", "mbar")
        self._set_value("Corrected Pressure", "--", "mbar")
        self._set_value("Target Pressure", "0.00", "mbar")
        controller.status_changed.connect(self._apply_status)
        controller.sample_ready.connect(self._apply_sample)

    def _set_value(self, name: str, value: str, unit: str = "") -> None:
        """Create or update one labeled sensor value row."""
        if name not in self._value_labels:
            row = self.grid.rowCount()
            title = CaptionLabel(name)
            title.setObjectName("V3MetricCaption")
            value_label = QLabel()
            value_label.setObjectName("V3MetricValue")
            unit_label = CaptionLabel(unit)
            self.grid.addWidget(title, row, 0)
            self.grid.addWidget(value_label, row, 1)
            self.grid.addWidget(unit_label, row, 2)
            self._value_labels[name] = value_label
        self._value_labels[name].setText(str(value))

    def _apply_status(self, status: dict) -> None:
        """Update status-derived values that do not require a fresh sample."""
        self._set_value("Target Pressure", f"{float(status.get('target_pressure', 0.0) or 0.0):.2f}", "mbar")
        self._set_value("Pressure Offset", f"{float(status.get('offset', 0.0) or 0.0):.3f}", "mbar")

    def _apply_sample(self, sample) -> None:
        """Update the card with the latest sampled values."""
        self._set_value("Measured Pressure", f"{float(sample.measured_pressure):.2f}", "mbar")
        self._set_value("Corrected Pressure", f"{float(sample.corrected_pressure):.2f}", "mbar")
        for name, value in sample.flow_values:
            self._set_value(name, self._format_number(value), "uL/min")
        for name, value in sample.fluigent_values:
            self._set_value(name, self._format_number(value), "mbar")
        for name, value, unit in sample.extra_values:
            self._set_value(name, self._format_number(value), unit)

    @staticmethod
    def _format_number(value) -> str:
        """Format numeric sensor values without hiding non-numeric telemetry."""
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return "--" if value is None else str(value)
