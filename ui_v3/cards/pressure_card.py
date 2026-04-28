"""Pressure control card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox

from ui_v3.fluent_compat import BodyLabel, CardWidget, CaptionLabel, PrimaryPushButton, PushButton, make_card_layout, stretch_row


class PressureCard(CardWidget):
    """Control the pressure setpoint through the runtime controller."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = make_card_layout(self)
        layout.addWidget(BodyLabel("Pressure Control"))
        layout.addWidget(CaptionLabel("Commands are sent through the runtime controller facade."))

        self.measured_label = CaptionLabel("Measured: -- mbar")
        self.corrected_label = CaptionLabel("Corrected: -- mbar")
        self.target_label = CaptionLabel("Target: 0.00 mbar")

        self.pressure = QDoubleSpinBox()
        self.pressure.setRange(-1000.0, 1000.0)
        self.pressure.setDecimals(2)
        self.pressure.setSuffix(" mbar")
        self.pressure.setSingleStep(5.0)

        self.offset = QDoubleSpinBox()
        self.offset.setRange(-1000.0, 1000.0)
        self.offset.setDecimals(3)
        self.offset.setSuffix(" mbar offset")
        self.offset.setSingleStep(1.0)

        self.set_button = PrimaryPushButton("Set Pressure")
        self.zero_button = PushButton("Set Pressure to Zero")
        self.set_offset_button = PushButton("Save Offset")
        self.zero_offset_button = PushButton("Zero From Internal Sensor")
        self.set_button.clicked.connect(lambda _checked=False: self._set_pressure())
        self.zero_button.clicked.connect(lambda _checked=False: self._zero_pressure())
        self.set_offset_button.clicked.connect(lambda _checked=False: self._set_offset())
        self.zero_offset_button.clicked.connect(lambda _checked=False: self.controller.zero_offset_from_internal_pressure())

        layout.addWidget(self.measured_label)
        layout.addWidget(self.corrected_label)
        layout.addWidget(self.target_label)
        layout.addWidget(self.pressure)
        layout.addWidget(stretch_row(self.set_button, self.zero_button))
        layout.addWidget(self.offset)
        layout.addWidget(stretch_row(self.set_offset_button, self.zero_offset_button))
        controller.status_changed.connect(self._apply_status)
        controller.sample_ready.connect(self._apply_sample)

    def _set_pressure(self) -> None:
        """Forward the selected setpoint to the controller."""
        self.controller.set_target_pressure_mbar(self.pressure.value())

    def _zero_pressure(self) -> None:
        """Use the hardware-zero path, matching the classic GUI semantics."""
        self.controller.reset_pressure_hardware_zero_mbar()
        self.pressure.setValue(0.0)

    def _set_offset(self) -> None:
        """Persist the offset selected by the user."""
        self.controller.set_offset_mbar(self.offset.value(), persist=True, ignore_persist_errors=True)

    def _apply_status(self, status: dict) -> None:
        """Reflect the current target when the user is not editing the field."""
        if not self.pressure.hasFocus():
            self.pressure.setValue(float(status.get("target_pressure", 0.0) or 0.0))
        if not self.offset.hasFocus():
            self.offset.setValue(float(status.get("offset", 0.0) or 0.0))
        self.target_label.setText(f"Target: {float(status.get('target_pressure', 0.0) or 0.0):.2f} mbar")

    def _apply_sample(self, sample) -> None:
        """Show the latest sampled pressure values."""
        self.measured_label.setText(f"Measured: {float(sample.measured_pressure):.2f} mbar")
        self.corrected_label.setText(f"Corrected: {float(sample.corrected_pressure):.2f} mbar")
