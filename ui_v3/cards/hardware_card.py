"""Hardware connection card for the v3 GUI."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QComboBox, QFileDialog, QMessageBox

from modules.mf_common import LOOKUP_DIR, load_hw_profile_from_prefs, load_last_modbus_ip
from ui_v3.fluent_compat import (
    CardWidget,
    CaptionLabel,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    add_info_header,
    make_card_layout,
    stretch_row,
)


class HardwareCard(CardWidget):
    """Expose the required hardware connection step in the main lab workflow."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._updating_profile_combo = False
        layout = make_card_layout(self)
        add_info_header(
            layout,
            "Hardware",
            "Connects the Modbus pressure/valve hardware and selects the active hardware profile. "
            "Refresh Config redetects supported sensors and updates the editor, plot, and CSV channel catalog.",
        )

        self.status = CaptionLabel("Status: disconnected")
        self.message = CaptionLabel("")
        self.ip = LineEdit()
        self.ip.setPlaceholderText("Modbus IP address, optional")
        last_ip = load_last_modbus_ip()
        if last_ip:
            self.ip.setText(str(last_ip))

        self.profile = QComboBox()
        self.profile.currentIndexChanged.connect(self._on_profile_selected)

        self.connect_button = PrimaryPushButton("Connect Hardware")
        self.disconnect_button = PushButton("Disconnect")
        self.refresh_button = PushButton("Refresh Config")
        self.refresh_profiles_button = PushButton("Profiles")
        self.open_profile_button = PushButton("Open JSON")
        self.connect_button.clicked.connect(lambda _checked=False: self._connect())
        self.disconnect_button.clicked.connect(lambda _checked=False: controller.disconnect_hardware())
        self.refresh_button.clicked.connect(lambda _checked=False: self._refresh_config())
        self.refresh_profiles_button.clicked.connect(lambda _checked=False: self._reload_profiles())
        self.open_profile_button.clicked.connect(lambda _checked=False: self._open_profile_file())

        layout.addWidget(self.status)
        layout.addWidget(self.message)
        layout.addWidget(self.ip)
        layout.addWidget(self.profile)
        layout.addWidget(stretch_row(self.refresh_profiles_button, self.open_profile_button))
        layout.addWidget(stretch_row(self.connect_button, self.disconnect_button, self.refresh_button))

        controller.status_changed.connect(self._apply_status)
        self._reload_profiles()
        self._apply_status(controller.status_snapshot())

    def _connect(self) -> None:
        """Connect using optional user-entered IP and selected profile values."""
        connected = self.controller.connect_hardware(
            self.ip.text().strip() or None,
            str(self.profile.currentData() or "").strip() or None,
        )
        if connected:
            self.message.setText("Connection established.")
        else:
            self.message.setText("Connection failed. Check Modbus IP, hardware power, and profile.")

    def _reload_profiles(self) -> None:
        """Reload profile choices from lookup and keep the active profile selected."""
        status = self.controller.status_snapshot()
        current = str(status.get("profile_source") or load_hw_profile_from_prefs(default="") or "")
        active_name = str(status.get("profile") or "")
        profiles = list(self.controller.available_hardware_profiles())

        self._updating_profile_combo = True
        self.profile.clear()
        for profile in profiles:
            self.profile.addItem(profile, profile)
        if current and self.profile.findData(current) < 0:
            label = active_name or os.path.basename(current)
            self.profile.addItem(f"{label} (external)", current)

        index = self.profile.findData(current)
        if index < 0 and active_name:
            index = self.profile.findText(active_name)
        if index >= 0:
            self.profile.setCurrentIndex(index)
        self._updating_profile_combo = False

    def _on_profile_selected(self, _index: int) -> None:
        """Apply profile changes immediately when hardware is already idle/connected."""
        if self._updating_profile_combo:
            return
        if not bool(self.controller.status_snapshot().get("connected")):
            return
        profile = str(self.profile.currentData() or "").strip()
        if not profile:
            return
        if not self.controller.set_hardware_profile(profile, persist=True):
            self._reload_profiles()

    def _open_profile_file(self) -> None:
        """Select an explicit profile JSON file."""
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open Hardware Profile",
            LOOKUP_DIR,
            "Hardware profile (*.json);;All files (*)",
        )
        if not path:
            return
        if bool(self.controller.status_snapshot().get("connected")):
            if not self.controller.set_hardware_profile(path, persist=True):
                QMessageBox.warning(self, "Hardware Profile", "The selected profile could not be applied.")
                return
            self._reload_profiles()
            return

        self._updating_profile_combo = True
        label = f"{os.path.basename(path)} (external)"
        existing = self.profile.findData(path)
        if existing < 0:
            self.profile.addItem(label, path)
            existing = self.profile.findData(path)
        self.profile.setCurrentIndex(existing)
        self._updating_profile_combo = False

    def _refresh_config(self) -> None:
        """Refresh detectable devices and show the summary in-place."""
        self.message.setText(str(self.controller.refresh_device_catalog()))

    def _apply_status(self, status: dict) -> None:
        """Keep controls aligned with the current connection state."""
        connected = bool(status.get("connected"))
        busy = bool(status.get("measuring")) or bool(status.get("program_running"))
        profile = status.get("profile") or "-"
        if connected:
            self.status.setText(f"Connected | Profile: {profile}")
        else:
            self.status.setText("Disconnected")
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.refresh_button.setEnabled(connected)
        self.ip.setEnabled(not connected)
        self.profile.setEnabled(not busy)
        self.refresh_profiles_button.setEnabled(not busy)
        self.open_profile_button.setEnabled(not busy)
        if str(self.profile.currentData() or "") != str(status.get("profile_source") or ""):
            self._reload_profiles()
