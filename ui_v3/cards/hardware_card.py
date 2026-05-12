"""Hardware connection card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from modules.mf_common import load_last_modbus_ip
from ui_v3.fluent_compat import (
    CardWidget,
    CaptionLabel,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    add_info_header,
    make_card_layout,
    mark_primary_action,
    stretch_row,
)


class HardwareCard(CardWidget):
    """Expose hardware connection and refresh controls without duplicating profile settings."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = make_card_layout(self)
        add_info_header(
            layout,
            "Hardware",
            "Connects the Modbus pressure/valve hardware using the profile selected in Hardware Profile settings. "
            "Refresh Config redetects supported sensors and updates the editor, plot, and CSV channel catalog.",
        )

        self.status = CaptionLabel("Status: disconnected")
        self.message = CaptionLabel("")
        self.ip = LineEdit()
        self.ip.setPlaceholderText("Modbus IP address, optional")
        last_ip = load_last_modbus_ip()
        if last_ip:
            self.ip.setText(str(last_ip))

        self.connect_button = mark_primary_action(PrimaryPushButton("Connect Hardware"))
        self.disconnect_button = PushButton("Disconnect")
        self.refresh_button = PushButton("Refresh Config")
        self.connect_button.clicked.connect(lambda _checked=False: self._connect())
        self.disconnect_button.clicked.connect(lambda _checked=False: controller.disconnect_hardware())
        self.refresh_button.clicked.connect(lambda _checked=False: self._refresh_config())

        layout.addWidget(self.status)
        layout.addWidget(self.message)
        layout.addWidget(QLabel("Modbus IP"))
        layout.addWidget(self.ip)
        layout.addWidget(stretch_row(self.connect_button, self.disconnect_button, self.refresh_button))

        controller.status_changed.connect(self._apply_status)
        self._apply_status(controller.status_snapshot())

    def _connect(self) -> None:
        """Connect using the optional user-entered IP and the persisted hardware profile."""
        connected = self.controller.connect_hardware(
            self.ip.text().strip() or None,
            None,
        )
        if connected:
            self.message.setText("Connection established.")
        else:
            self.message.setText("Connection failed. Check Modbus IP, hardware power, and profile.")

    def _refresh_config(self) -> None:
        """Refresh detectable devices and show the summary in-place."""
        self.message.setText(str(self.controller.refresh_device_catalog()))

    def _apply_status(self, status: dict) -> None:
        """Keep controls aligned with the current connection state."""
        connected = bool(status.get("connected"))
        profile = status.get("profile") or "-"
        if connected:
            self.status.setText(f"Connected | Profile: {profile}")
        else:
            self.status.setText("Disconnected")
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.refresh_button.setEnabled(connected)
        self.ip.setEnabled(not connected)
