"""Settings and device refresh card for the v3 GUI."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFileDialog, QInputDialog, QMessageBox

from modules.mf_common import LOOKUP_DIR
from ui_v3.fluent_compat import (
    BodyLabel,
    CardWidget,
    CaptionLabel,
    PushButton,
    make_card_layout,
    stretch_row,
)


class SettingsCard(CardWidget):
    """Pressure-offset settings kept away from the main cockpit."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._updating_profile_combo = False
        layout = make_card_layout(self)
        layout.addWidget(BodyLabel("Hardware Profile"))
        layout.addWidget(CaptionLabel("Choose the valve mapping used by the GUI, editor, plot, and CSV export."))

        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        self.refresh_profiles_button = PushButton("Refresh List")
        self.open_profile_button = PushButton("Open Profile JSON...")
        self.refresh_profiles_button.clicked.connect(lambda _checked=False: self._reload_profiles())
        self.open_profile_button.clicked.connect(lambda _checked=False: self._open_profile_file())

        layout.addWidget(self.profile_combo)
        layout.addWidget(stretch_row(self.refresh_profiles_button, self.open_profile_button))

        layout.addWidget(BodyLabel("Pressure Offset"))
        layout.addWidget(CaptionLabel("Offset calibration and persistence."))

        self.offset = QDoubleSpinBox()
        self.offset.setRange(-1000.0, 1000.0)
        self.offset.setDecimals(3)
        self.offset.setSuffix(" mbar")
        self.offset.setSingleStep(1.0)
        self.offset.lineEdit().returnPressed.connect(self._save_offset)

        self.save_offset_button = PushButton("Save Offset")
        self.zero_internal_button = PushButton("Zero From Internal")
        self.offset_button = PushButton("Calibrate Offset...")

        self.save_offset_button.clicked.connect(lambda _checked=False: self._save_offset())
        self.zero_internal_button.clicked.connect(lambda _checked=False: self.controller.zero_offset_from_internal_pressure())
        self.offset_button.clicked.connect(lambda _checked=False: self._calibrate_offset())

        layout.addWidget(self.offset)
        layout.addWidget(stretch_row(self.save_offset_button, self.zero_internal_button))
        layout.addWidget(self.offset_button)
        controller.status_changed.connect(self._apply_status)
        self._reload_profiles()
        self._apply_status(controller.status_snapshot())

    def _reload_profiles(self) -> None:
        """Reload profile names from lookup and keep the active item selected."""
        current = str(self.controller.status_snapshot().get("profile_source") or "")
        active_name = str(self.controller.status_snapshot().get("profile") or "")
        profiles = list(self.controller.available_hardware_profiles())
        self._updating_profile_combo = True
        self.profile_combo.clear()
        for profile in profiles:
            self.profile_combo.addItem(profile, profile)
        if current and self.profile_combo.findData(current) < 0:
            label = active_name or os.path.basename(current)
            self.profile_combo.addItem(f"{label} (external)", current)

        selected_index = self.profile_combo.findData(current)
        if selected_index < 0 and active_name:
            selected_index = self.profile_combo.findText(active_name)
        if selected_index >= 0:
            self.profile_combo.setCurrentIndex(selected_index)
        self._updating_profile_combo = False

    def _on_profile_selected(self, _index: int) -> None:
        """Apply a profile selected from the lookup dropdown."""
        if self._updating_profile_combo:
            return
        profile = self.profile_combo.currentData()
        if not profile:
            return
        if not self.controller.set_hardware_profile(str(profile), persist=True):
            self._reload_profiles()

    def _open_profile_file(self) -> None:
        """Load an explicit profile JSON file selected by the user."""
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open Hardware Profile",
            LOOKUP_DIR,
            "Hardware profile (*.json);;All files (*)",
        )
        if not path:
            return
        if self.controller.set_hardware_profile(path, persist=True):
            self._reload_profiles()
        else:
            QMessageBox.warning(self, "Hardware Profile", "The selected profile could not be applied.")

    def _save_offset(self) -> None:
        """Persist the manually entered pressure offset."""
        self.controller.set_offset_mbar(self.offset.value(), persist=True, ignore_persist_errors=True)

    def _apply_status(self, status: dict) -> None:
        """Keep the offset field aligned unless the user is editing it."""
        if str(self.profile_combo.currentData() or "") != str(status.get("profile_source") or ""):
            self._reload_profiles()
        if not self.offset.hasFocus():
            self.offset.setValue(float(status.get("offset", 0.0) or 0.0))
        connected = bool(status.get("connected"))
        busy = bool(status.get("measuring")) or bool(status.get("program_running"))
        self.profile_combo.setEnabled(not busy)
        self.refresh_profiles_button.setEnabled(not busy)
        self.open_profile_button.setEnabled(not busy)
        self.offset.setEnabled(connected)
        self.save_offset_button.setEnabled(connected)
        self.zero_internal_button.setEnabled(connected)
        self.offset_button.setEnabled(connected)

    def _calibrate_offset(self) -> None:
        """Open the v2-style pressure-offset calibration dialog."""
        options = ["Internal pressure monitor"]
        sensor_by_label = {}
        for sensor in getattr(self.controller, "fluigent_sensors", []) or []:
            device_sn = str(getattr(sensor, "device_sn", "") or "")
            label = f"Fluigent SN{device_sn}" if device_sn else "Fluigent sensor"
            sensor_by_label[label] = sensor
            options.append(label)

        choice, ok = QInputDialog.getItem(
            self,
            "Offset Calibration",
            "Choose calibration source:",
            options,
            0,
            False,
        )
        if not ok:
            return

        if choice == "Internal pressure monitor":
            value = self.controller.zero_offset_from_internal_pressure(persist=True)
            if value is None:
                QMessageBox.warning(self, "Offset", "Internal pressure monitor is not readable.")
                return
            QMessageBox.information(self, "Offset", f"Offset set to {value:.3f} mbar.")
            return

        sensor = sensor_by_label.get(choice)
        if sensor is None:
            return
        internal = self.controller.read_internal_pressure_mbar()
        if internal is None:
            QMessageBox.warning(self, "Offset", "Internal pressure monitor is not readable.")
            return
        try:
            reference = sensor.read_pressure()
        except Exception as exc:
            QMessageBox.warning(self, "Offset", f"Fluigent read failed: {exc}")
            return
        if reference is None:
            QMessageBox.warning(self, "Offset", "Selected Fluigent sensor returned no value.")
            return

        offset = float(internal) - float(reference)
        self.controller.set_offset_mbar(offset, persist=True, ignore_persist_errors=True)
        QMessageBox.information(
            self,
            "Offset",
            f"Offset set to {offset:.3f} mbar using {choice}.",
        )
