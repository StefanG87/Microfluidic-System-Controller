"""Standalone entry point for the program editor."""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOOKUP_DIR = os.path.join(PROJECT_ROOT, "lookup")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QShortcut,
    QVBoxLayout,
    QWidget,
)

from editor.modules.editor import task_globals
from editor.modules.editor.editor_joblist import EditorJobList
from editor.modules.editor.editor_step import Step
from editor.modules.editor.editor_tasklist import EditorTaskList
from modules.mf_common import (
    list_hw_profiles,
    load_hardware_profile,
    load_hw_profile_from_prefs,
    save_hw_profile_to_prefs,
)
from modules.device_catalog import (
    DeviceCatalog,
    describe_internal_pressure_sensor,
    describe_valve,
    register_default_flow_sensors,
    valve_meta_from_profile_item,
)


def _profile_json_path(profile_name: str) -> str:
    """Return the absolute JSON path for a named hardware profile."""
    return os.path.join(LOOKUP_DIR, f"{profile_name}.json")


def _set_editor_devices_from_profile(profile_name: str):
    """Load a profile, publish editor valve names, and expose generic standalone sensors."""
    prof = load_hardware_profile(_profile_json_path(profile_name))
    catalog = DeviceCatalog()
    catalog.register_sensor_descriptor(describe_internal_pressure_sensor())
    register_default_flow_sensors(catalog)

    for group in prof.get("valve_groups", []):
        for item in group.get("items", []):
            catalog.register_actuator_descriptor(
                describe_valve(valve_meta_from_profile_item(group, item))
            )

    valve_names = catalog.valve_names()
    sensor_names = catalog.sensor_names()

    if hasattr(task_globals, "update_available_valves"):
        task_globals.update_available_valves(valve_names)
    else:
        task_globals.AVAILABLE_VALVES = valve_names

    if hasattr(task_globals, "update_available_sensors"):
        task_globals.update_available_sensors(sensor_names)
    else:
        task_globals.AVAILABLE_SENSORS = sensor_names

    return {
        "name": prof.get("name", profile_name),
        **catalog.to_embedded_editor_info(),
    }


class EditorMain(QWidget):
    """Main window for the standalone program editor."""

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Microfluidic Program Editor")
        self.setGeometry(100, 100, 1200, 600)

        root = QVBoxLayout(self)

        topbar = QHBoxLayout()
        topbar.addStretch()
        topbar.addWidget(QLabel("Profile:"))

        self.cmb_profile = QComboBox()
        profiles = list_hw_profiles(LOOKUP_DIR) or ["stand1", "stand2"]
        self.cmb_profile.addItems(profiles)

        current = load_hw_profile_from_prefs(default="stand1")
        idx = self.cmb_profile.findText(str(current))
        if idx >= 0:
            self.cmb_profile.setCurrentIndex(idx)

        topbar.addWidget(self.cmb_profile)
        topbar.addStretch()
        root.addLayout(topbar)

        main = QHBoxLayout()
        root.addLayout(main, 1)

        self.tasklist = EditorTaskList(self.add_task)
        main.addWidget(self.tasklist, 1)

        self.joblist = EditorJobList()
        self._sc_save = QShortcut(QKeySequence.Save, self)
        self._sc_save.activated.connect(self.joblist.save_program)
        main.addWidget(self.joblist, 3)

        info = _set_editor_devices_from_profile(self.cmb_profile.currentText())
        self._set_title_with_profile(info.get("name", self.cmb_profile.currentText()))

        self.cmb_profile.currentIndexChanged.connect(self._on_profile_changed)
        self.setLayout(root)

    def _set_title_with_profile(self, prof_name: str):
        self.setWindowTitle(f"Microfluidic Program Editor - [{prof_name}]")

    def _on_profile_changed(self, _index: int):
        name = self.cmb_profile.currentText().strip()
        if not name:
            return

        ok = save_hw_profile_to_prefs(name)
        if not ok:
            QMessageBox.warning(
                self,
                "Save Error",
                "Could not save the selected profile to lookup/device_prefs.json",
            )

        info = _set_editor_devices_from_profile(name)
        self._set_title_with_profile(info.get("name", name))

    def add_task(self, task_name):
        new_step = Step(task_name)
        self.joblist.add_step(new_step)


def main() -> int:
    """Launch the standalone editor application."""
    app = QApplication(sys.argv)
    window = EditorMain()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
