"""Pressure control card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QMessageBox

from ui_v3.fluent_compat import CardWidget, CaptionLabel, LineEdit, PrimaryPushButton, PushButton, add_info_header, make_card_layout, mark_primary_action, stretch_row


class PressureCard(CardWidget):
    """Control the pressure setpoint through the runtime controller."""

    def __init__(
        self,
        controller,
        parent=None,
        show_offset_controls: bool = False,
        compact_status: bool = False,
    ):
        super().__init__(parent)
        self.controller = controller
        self.show_offset_controls = bool(show_offset_controls)
        self.compact_status = bool(compact_status)
        self._measured_text = "-- mbar"
        self._corrected_text = "-- mbar"
        self._target_text = "0.00 mbar"
        layout = make_card_layout(self)
        add_info_header(
            layout,
            "Pressure Control",
            "Set Pressure sends a compensated pressure setpoint through the runtime controller. "
            "Set Pressure to Zero uses the hardware-zero path and removes pressure output, matching the classic GUI behavior.",
        )

        self.measured_label = CaptionLabel("Measured: -- mbar")
        self.corrected_label = CaptionLabel("Corrected: -- mbar")
        self.target_label = CaptionLabel("Target: 0.00 mbar")
        self.status_label = CaptionLabel("Measured: -- mbar | Corrected: -- mbar | Target: 0.00 mbar")

        self.pressure = LineEdit()
        self.pressure.setPlaceholderText("Target pressure [mbar]")
        self.pressure.setText("0.00")
        self.pressure.returnPressed.connect(self._set_pressure)

        self.offset = None
        self.set_offset_button = None
        self.zero_offset_button = None
        if self.show_offset_controls:
            self.offset = QDoubleSpinBox()
            self.offset.setRange(-1000.0, 1000.0)
            self.offset.setDecimals(3)
            self.offset.setSuffix(" mbar offset")
            self.offset.setSingleStep(1.0)
            self.offset.lineEdit().returnPressed.connect(self._set_offset)

        self.set_button = mark_primary_action(PrimaryPushButton("Set Pressure"))
        self.zero_button = PushButton("Set Pressure to Zero")
        self.set_button.clicked.connect(lambda _checked=False: self._set_pressure())
        self.zero_button.clicked.connect(lambda _checked=False: self._zero_pressure())
        if self.show_offset_controls:
            self.set_offset_button = PushButton("Save Offset")
            self.zero_offset_button = PushButton("Zero From Internal Sensor")
            self.set_offset_button.clicked.connect(lambda _checked=False: self._set_offset())
            self.zero_offset_button.clicked.connect(lambda _checked=False: self.controller.zero_offset_from_internal_pressure())

        if self.compact_status:
            layout.addWidget(self.status_label)
        else:
            layout.addWidget(self.measured_label)
            layout.addWidget(self.corrected_label)
            layout.addWidget(self.target_label)
        layout.addWidget(self.pressure)
        layout.addWidget(stretch_row(self.set_button, self.zero_button))
        if self.show_offset_controls:
            layout.addWidget(self.offset)
            layout.addWidget(stretch_row(self.set_offset_button, self.zero_offset_button))
        controller.status_changed.connect(self._apply_status)
        controller.sample_ready.connect(self._apply_sample)
        self._apply_status(controller.status_snapshot())

    def _set_pressure(self) -> None:
        """Forward the selected setpoint to the controller."""
        value = self._pressure_value()
        if value is None:
            return
        self.controller.set_target_pressure_mbar(value)

    def _zero_pressure(self) -> None:
        """Use the hardware-zero path, matching the classic GUI semantics."""
        self.controller.reset_pressure_hardware_zero_mbar()
        self.pressure.setText("0.00")

    def _pressure_value(self) -> float | None:
        """Parse the entered pressure while accepting decimal comma or dot."""
        text = self.pressure.text().strip().replace(",", ".")
        if text.lower().endswith("mbar"):
            text = text[:-4].strip()
        try:
            value = float(text)
        except ValueError:
            QMessageBox.warning(self, "Pressure", "Please enter a valid pressure in mbar.")
            return None
        if not -1000.0 <= value <= 1000.0:
            QMessageBox.warning(self, "Pressure", "Pressure must be between -1000 and 1000 mbar.")
            return None
        return value

    def _set_offset(self) -> None:
        """Persist the offset selected by the user."""
        if self.offset is not None:
            self.controller.set_offset_mbar(self.offset.value(), persist=True, ignore_persist_errors=True)

    def _apply_status(self, status: dict) -> None:
        """Reflect the current target when the user is not editing the field."""
        if not self.pressure.hasFocus():
            self.pressure.setText(f"{float(status.get('target_pressure', 0.0) or 0.0):.2f}")
        if self.offset is not None and not self.offset.hasFocus():
            self.offset.setValue(float(status.get("offset", 0.0) or 0.0))
        self._target_text = f"{float(status.get('target_pressure', 0.0) or 0.0):.2f} mbar"
        self.target_label.setText(f"Target: {self._target_text}")
        self._update_compact_status()
        connected = bool(status.get("connected"))
        self.pressure.setEnabled(connected)
        self.set_button.setEnabled(connected)
        self.zero_button.setEnabled(connected)
        if self.offset is not None:
            self.offset.setEnabled(connected)
        if self.set_offset_button is not None:
            self.set_offset_button.setEnabled(connected)
        if self.zero_offset_button is not None:
            self.zero_offset_button.setEnabled(connected)

    def _apply_sample(self, sample) -> None:
        """Show the latest sampled pressure values."""
        self._measured_text = f"{float(sample.measured_pressure):.2f} mbar"
        self._corrected_text = f"{float(sample.corrected_pressure):.2f} mbar"
        self.measured_label.setText(f"Measured: {self._measured_text}")
        self.corrected_label.setText(f"Corrected: {self._corrected_text}")
        self._update_compact_status()

    def _update_compact_status(self) -> None:
        """Keep the single-line dashboard pressure summary up to date."""
        if not self.compact_status:
            return
        self.status_label.setText(
            f"Measured: {self._measured_text} | "
            f"Corrected: {self._corrected_text} | "
            f"Target: {self._target_text}"
        )
