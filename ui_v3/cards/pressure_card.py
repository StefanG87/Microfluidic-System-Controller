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

        self.pressure = QDoubleSpinBox()
        self.pressure.setRange(-1000.0, 1000.0)
        self.pressure.setDecimals(2)
        self.pressure.setSuffix(" mbar")
        self.pressure.setSingleStep(5.0)

        self.set_button = PrimaryPushButton("Set Pressure")
        self.zero_button = PushButton("Set Pressure to Zero")
        self.set_button.clicked.connect(lambda _checked=False: self._set_pressure())
        self.zero_button.clicked.connect(lambda _checked=False: self._zero_pressure())

        layout.addWidget(self.pressure)
        layout.addWidget(stretch_row(self.set_button, self.zero_button))
        controller.status_changed.connect(self._apply_status)

    def _set_pressure(self) -> None:
        """Forward the selected setpoint to the controller."""
        self.controller.set_target_pressure_mbar(self.pressure.value())

    def _zero_pressure(self) -> None:
        """Use the hardware-zero path, matching the classic GUI semantics."""
        self.controller.reset_pressure_hardware_zero_mbar()
        self.pressure.setValue(0.0)

    def _apply_status(self, status: dict) -> None:
        """Reflect the current target when the user is not editing the field."""
        if not self.pressure.hasFocus():
            self.pressure.setValue(float(status.get("target_pressure", 0.0) or 0.0))
