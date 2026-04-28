"""Settings and device refresh card for the v3 GUI."""

from __future__ import annotations

from ui_v3.fluent_compat import (
    BodyLabel,
    CardWidget,
    CaptionLabel,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    Theme,
    isDarkTheme,
    make_card_layout,
    setTheme,
    stretch_row,
)


class SettingsCard(CardWidget):
    """Connect hardware, refresh the catalog, and switch theme."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = make_card_layout(self)
        layout.addWidget(BodyLabel("Settings"))
        layout.addWidget(CaptionLabel("Hardware discovery is manual to keep startup safe in the lab."))

        self.ip = LineEdit()
        self.ip.setPlaceholderText("Modbus IP address, optional")
        self.profile = LineEdit()
        self.profile.setPlaceholderText("Hardware profile, optional (for example: stand1)")
        self.connect_button = PrimaryPushButton("Connect Hardware")
        self.disconnect_button = PushButton("Disconnect")
        self.refresh_button = PushButton("Refresh Config")
        self.theme_button = PushButton("Toggle Theme")

        self.connect_button.clicked.connect(lambda _checked=False: self._connect())
        self.disconnect_button.clicked.connect(lambda _checked=False: controller.disconnect_hardware())
        self.refresh_button.clicked.connect(lambda _checked=False: controller.refresh_device_catalog())
        self.theme_button.clicked.connect(lambda _checked=False: self._toggle_theme())

        layout.addWidget(self.ip)
        layout.addWidget(self.profile)
        layout.addWidget(stretch_row(self.connect_button, self.disconnect_button))
        layout.addWidget(stretch_row(self.refresh_button, self.theme_button))
        controller.status_changed.connect(self._apply_status)

    def _connect(self) -> None:
        """Connect using the optional IP entered by the user."""
        self.controller.connect_hardware(
            self.ip.text().strip() or None,
            self.profile.text().strip() or None,
        )

    def _toggle_theme(self) -> None:
        """Switch Fluent theme; fallback CSS remains dark during early v3 work."""
        setTheme(Theme.LIGHT if isDarkTheme() else Theme.DARK)

    def _apply_status(self, status: dict) -> None:
        """Reflect the connection state in command availability."""
        connected = bool(status.get("connected"))
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.refresh_button.setEnabled(connected)
