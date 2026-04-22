"""Integrated program editor window used by the main controller GUI."""

import sys
from types import SimpleNamespace

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QShortcut, QWidget

from editor.modules.editor.editor_joblist import EditorJobList
from editor.modules.editor.editor_step import Step
from editor.modules.editor.editor_tasklist import EditorTaskList
from editor.modules.editor.task_globals import update_available_sensors, update_available_valves
from modules.device_catalog import (
    DeviceCatalog,
    SENSOR_NAME_INTERNAL,
    describe_fluigent_sensor,
    describe_internal_pressure_sensor,
    describe_valve,
    register_default_flow_sensors,
)


class EmbeddedEditorWindow(QWidget):
    """Program editor window launched from the main GUI."""

    def __init__(self, device_info: dict):
        super().__init__()
        self.setWindowTitle("Program Editor (Integrated)")
        self.setGeometry(150, 150, 1200, 600)

        self.device_info = device_info
        self.override_device_context()

        layout = QHBoxLayout(self)

        self.tasklist = EditorTaskList(self.add_task)
        layout.addWidget(self.tasklist, 1)

        self.joblist = EditorJobList()
        layout.addWidget(self.joblist, 3)
        self._sc_save = QShortcut(QKeySequence.Save, self)
        self._sc_save.activated.connect(self.joblist.save_program)

    def add_task(self, task_name):
        """Create a new step from the selected task and append it to the job list."""
        new_step = Step(task_name)
        self.joblist.add_step(new_step)

    def override_device_context(self):
        """Publish the currently available sensors and valves for editor dialogs."""
        sensor_names = list(self.device_info.get("sensors", []))
        if not sensor_names:
            sensor_names.extend(self.device_info.get("flow_sensors", []))
            sensor_names.extend(self.device_info.get("fluigent_sensors", []))
        if SENSOR_NAME_INTERNAL not in sensor_names:
            sensor_names.insert(0, SENSOR_NAME_INTERNAL)

        valve_names = list(self.device_info.get("valve_names", []))
        if not valve_names:
            valve_count = int(self.device_info.get("valves", 0) or 0)
            valve_names = [str(index) for index in range(1, valve_count + 1)]

        update_available_sensors(sensor_names)
        update_available_valves(valve_names)


def _build_dummy_device_info() -> dict:
    """Return a small standalone preview context for manual editor checks."""
    catalog = DeviceCatalog()
    catalog.register_sensor_descriptor(describe_internal_pressure_sensor())
    register_default_flow_sensors(catalog, count=2)
    catalog.register_sensor_descriptor(
        describe_fluigent_sensor(SimpleNamespace(device_sn="12345"), 0)
    )
    for name in ("Pneumatic 1", "Pneumatic 2", "Fluidic 1", "Fluidic 2"):
        catalog.register_actuator_descriptor(
            describe_valve(
                {
                    "editor_name": name,
                    "button_label": name,
                    "group": "",
                    "coil": 0,
                    "box": "Valves",
                }
            )
        )
    return catalog.to_embedded_editor_info()


def main() -> int:
    """Launch the integrated editor in standalone preview mode."""
    app = QApplication(sys.argv)
    window = EmbeddedEditorWindow(_build_dummy_device_info())
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
