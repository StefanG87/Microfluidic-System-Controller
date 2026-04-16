"""Program step list and editing controls for the editor."""

import json
import os
from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from .editor_step import Step
from .special_tasks import SpecialTasks


class EditorJobList(QWidget):
    """Manage the editable program step list shown on the right side of the editor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []
        self.undo_stack = []
        self.redo_stack = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        button_row = QHBoxLayout()

        icon_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "icons"))

        self.btn_save = QPushButton()
        self.btn_save.setIcon(QIcon(os.path.join(icon_folder, "save.png")))
        self.btn_save.setToolTip("Save Program")
        self.btn_save.setMaximumSize(32, 32)
        self.btn_save.clicked.connect(self.save_program)
        button_row.addWidget(self.btn_save)

        self.btn_load = QPushButton()
        self.btn_load.setIcon(QIcon(os.path.join(icon_folder, "open.png")))
        self.btn_load.setToolTip("Load Program")
        self.btn_load.setMaximumSize(32, 32)
        self.btn_load.clicked.connect(self.load_program)
        button_row.addWidget(self.btn_load)

        self.btn_undo = QPushButton()
        self.btn_undo.setIcon(QIcon(os.path.join(icon_folder, "undo.png")))
        self.btn_undo.setToolTip("Undo")
        self.btn_undo.setMaximumSize(32, 32)
        self.btn_undo.clicked.connect(self.undo)
        button_row.addWidget(self.btn_undo)

        self.btn_redo = QPushButton()
        self.btn_redo.setIcon(QIcon(os.path.join(icon_folder, "redo.png")))
        self.btn_redo.setToolTip("Redo")
        self.btn_redo.setMaximumSize(32, 32)
        self.btn_redo.clicked.connect(self.redo)
        button_row.addWidget(self.btn_redo)

        main_layout.addLayout(button_row)

        self.job_list = QListWidget()
        self.job_list.setSelectionMode(QListWidget.ExtendedSelection)
        main_layout.addWidget(self.job_list)

        self.btn_move_up = QPushButton("Move Up")
        self.btn_move_up.clicked.connect(self.move_step_up)
        main_layout.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("Move Down")
        self.btn_move_down.clicked.connect(self.move_step_down)
        main_layout.addWidget(self.btn_move_down)

        self.btn_copy = QPushButton("Copy Selected")
        self.btn_copy.clicked.connect(self.copy_selected_steps)
        main_layout.addWidget(self.btn_copy)

        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.clicked.connect(self.delete_selected_steps)
        main_layout.addWidget(self.btn_delete)

    def add_step(self, step):
        self.save_state()
        self.steps.append(step)
        self.refresh_joblist()

    def refresh_joblist(self):
        """Rebuild the visible job list from the current step state."""
        self.job_list.clear()
        self.update_step_numbers()

        for index, step in enumerate(self.steps, start=1):
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(5, 2, 5, 2)

            checkbox = QCheckBox()
            checkbox.setChecked(step.active)
            checkbox.stateChanged.connect(partial(self.toggle_active, step))

            label = QLabel(f"{index}. {self.format_step_text(step)}")

            edit_button = QPushButton("\u270E")
            edit_button.setMaximumWidth(30)
            edit_button.clicked.connect(partial(self.edit_step, step))

            item_layout.addWidget(checkbox)
            item_layout.addWidget(label)
            item_layout.addStretch()

            if step.type == "Flow Controller":
                pid_button = QPushButton("\U0001F6E0")
                pid_button.setMaximumWidth(30)
                pid_button.clicked.connect(partial(self.edit_pid_parameters, step))
                item_layout.addWidget(pid_button)

            if step.type == "Valve":
                toggle_button = self.create_toggle_button(step)
                item_layout.addWidget(toggle_button)

            item_layout.addWidget(edit_button)

            item = QListWidgetItem(self.job_list)
            item.setSizeHint(item_widget.sizeHint())
            self.job_list.addItem(item)
            self.job_list.setItemWidget(item, item_widget)

    def create_toggle_button(self, step):
        """Create the quick-toggle button for valve steps."""
        toggle_button = QPushButton("\U0001F501")
        toggle_button.setMaximumWidth(30)
        toggle_button.clicked.connect(partial(self.toggle_valve, step))
        return toggle_button

    def format_step_text(self, step):
        """Return the human-readable summary shown for one step."""
        if step.type == "Set Pressure":
            pressure = step.params.get("pressure", 0.0)
            return f"Set Pressure ({pressure} mbar)"

        if step.type == "Add Pressure":
            delta = step.params.get("delta_mbar", 0.0)
            return f"Add Pressure (+{delta} mbar)"

        if step.type == "Valve":
            valve_name = step.params.get("valve_name", "Unknown")
            status = step.params.get("status", "Open")
            return f"Valve {valve_name} ({status})"

        if step.type == "Wait":
            time_sec = step.params.get("time_sec", 1.0)
            return f"Wait ({time_sec} s)"

        if step.type == "Wait for Sensor Event":
            sensor = step.params.get("sensor", "Unknown")
            condition = step.params.get("condition", ">")
            target_value = step.params.get("target_value", 0.0)
            tolerance = step.params.get("tolerance", 0.0)
            stable_time = step.params.get("stable_time", 0.0)
            return f"Sensor {sensor} {condition} {target_value} (+/-{tolerance}, {stable_time}s)"

        if step.type == "Start Measurement":
            sampling_rate = step.params.get("sampling_rate", 10)
            return f"Start Measurement (Rate: {sampling_rate} Hz)"

        if step.type == "Stop Measurement":
            return "Stop Measurement"

        if step.type == "Export CSV":
            prefix = step.params.get("filename_prefix", "Measurement")
            return f"Export CSV (Prefix: {prefix})"

        if step.type == "Pressure Ramp":
            return (
                f"Pressure Ramp ({step.params.get('start_pressure', 0.0)} -> "
                f"{step.params.get('end_pressure', 100.0)} mbar)"
            )

        if step.type == "Flow Controller":
            target_flow = step.params.get("target_flow", 50.0)
            max_pressure = step.params.get("max_pressure", 350.0)
            min_pressure = step.params.get("min_pressure", 0.0)
            tolerance = step.params.get("tolerance_percent", 10.0)
            continuous = "Continuous" if step.params.get("continuous", False) else "Stable"

            if "Kp" in step.params:
                kp = step.params.get("Kp", 0.1)
                ki = step.params.get("Ki", 0.1)
                kd = step.params.get("Kd", 0.05)
                return (
                    f"Flow Controller (Target: {target_flow} uL/min, Max: {max_pressure} mbar, "
                    f"Min: {min_pressure} mbar, Tolerance: +/-{tolerance}%, {continuous}, "
                    f"PID: Kp={kp}, Ki={ki}, Kd={kd})"
                )

            return (
                f"Flow Controller (Target: {target_flow} uL/min, Max: {max_pressure} mbar, "
                f"Min: {min_pressure} mbar, Tolerance: +/-{tolerance}%, {continuous})"
            )

        if step.type == "ZeroFluigent":
            sensor_list = step.params.get("sensors", [])
            if not sensor_list:
                return "Zero Fluigent Sensors (All)"
            return f"Zero Fluigent Sensors ({', '.join(sensor_list)})"

        if step.type == "Calibrate With Fluigent Sensor":
            sensor_name = step.params.get("sensor", "Unknown")
            return f"Calibrate With {sensor_name}"

        if step.type == "Loop":
            start_step = step.params.get("start_step", 1)
            end_step = step.params.get("end_step", 1)
            repetitions = step.params.get("repetitions", 1)
            return f"Loop (Steps {start_step}-{end_step}, {repetitions}x)"

        if step.type == "Load Sequence":
            filename = step.params.get("filename", "Unknown")
            return f"Load Sequence ({filename})"

        if step.type == "Dose Volume":
            volume = step.params.get("target_volume", 100.0)
            pneumatic_valve = step.params.get("pneumatic_valve", "?")
            fluidic_valve = step.params.get("fluidic_valve", "?")
            pressure = step.params.get("input_pressure", "?")
            return f"Dose {volume} uL @ {pressure} mbar ({pneumatic_valve} -> {fluidic_valve})"

        if step.type == "Rotary Valve":
            action = step.params.get("action", "goto")
            if action == "goto":
                port = step.params.get("port", 1)
                wait = step.params.get("wait", True)
                return f"Rotary Valve (Goto {port}, wait={wait})"
            return f"Rotary Valve ({action})"

        return f"{step.type}"

    def toggle_active(self, step, state):
        step.active = (state == Qt.Checked)

    def toggle_valve(self, step):
        """Switch a valve step between Open and Close."""
        self.save_state()
        if step.type == "Valve":
            if step.params.get("status") == "Open":
                step.params["status"] = "Close"
            else:
                step.params["status"] = "Open"
            self.refresh_joblist()

    def edit_step(self, step):
        """Open the appropriate parameter editor for the selected step."""
        self.save_state()

        from .editor_tasks import EditorTasks

        if step.type in SpecialTasks.get_all_task_names():
            SpecialTasks.edit_task_params(self, step)
        elif step.type in EditorTasks.get_all_task_names():
            EditorTasks.edit_task_params(self, step)
        else:
            print(f"[Editor] Unknown step type: {step.type}")

        self.refresh_joblist()

    def edit_pid_parameters(self, step):
        """Edit PID gains for a flow controller step."""
        if step.type != "Flow Controller":
            QMessageBox.warning(self, "Error", "PID parameters are only available for Flow Controller.")
            return

        kp, ok = QInputDialog.getDouble(
            self, "PID Parameter", "Kp (Proportional):", step.params.get("Kp", 0.1)
        )
        if not ok:
            return

        ki, ok = QInputDialog.getDouble(
            self, "PID Parameter", "Ki (Integral):", step.params.get("Ki", 0.1)
        )
        if not ok:
            return

        kd, ok = QInputDialog.getDouble(
            self, "PID Parameter", "Kd (Derivative):", step.params.get("Kd", 0.05)
        )
        if not ok:
            return

        step.params["Kp"] = kp
        step.params["Ki"] = ki
        step.params["Kd"] = kd
        self.refresh_joblist()

    def copy_selected_steps(self):
        selected_items = self.job_list.selectedItems()
        if not selected_items:
            return

        self.save_state()

        for item in selected_items:
            index = self.job_list.row(item)
            copied_step = Step(self.steps[index].type, dict(self.steps[index].params))
            copied_step.active = self.steps[index].active
            self.steps.append(copied_step)

        self.refresh_joblist()

    def delete_selected_steps(self):
        selected_items = self.job_list.selectedItems()
        if not selected_items:
            return

        reply = QMessageBox.question(self, "Confirm Delete", "Delete selected steps?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.save_state()
            indices = sorted([self.job_list.row(item) for item in selected_items], reverse=True)
            for idx in indices:
                del self.steps[idx]
            self.refresh_joblist()

    def move_step_up(self):
        current_row = self.job_list.currentRow()
        if current_row > 0:
            self.save_state()
            self.steps[current_row], self.steps[current_row - 1] = self.steps[current_row - 1], self.steps[current_row]
            self.refresh_joblist()
            self.job_list.setCurrentRow(current_row - 1)

    def move_step_down(self):
        current_row = self.job_list.currentRow()
        if 0 <= current_row < len(self.steps) - 1:
            self.save_state()
            self.steps[current_row], self.steps[current_row + 1] = self.steps[current_row + 1], self.steps[current_row]
            self.refresh_joblist()
            self.job_list.setCurrentRow(current_row + 1)

    def save_state(self):
        state = json.dumps([{"type": s.type, "params": s.params, "active": s.active} for s in self.steps])
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            current_state = json.dumps([{"type": s.type, "params": s.params, "active": s.active} for s in self.steps])
            self.redo_stack.append(current_state)
            last_state = self.undo_stack.pop()
            data = json.loads(last_state)
            self.steps = [Step(item["type"], item["params"]) for item in data]
            for step, item in zip(self.steps, data):
                step.active = item.get("active", True)
            self.refresh_joblist()

    def redo(self):
        if self.redo_stack:
            current_state = json.dumps([{"type": s.type, "params": s.params, "active": s.active} for s in self.steps])
            self.undo_stack.append(current_state)
            next_state = self.redo_stack.pop()
            data = json.loads(next_state)
            self.steps = [Step(item["type"], item["params"]) for item in data]
            for step, item in zip(self.steps, data):
                step.active = item.get("active", True)
            self.refresh_joblist()

    def save_program(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Program", "", "JSON Files (*.json)")
        if path:
            data = [{"type": s.type, "params": s.params, "active": s.active} for s in self.steps]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

    def load_program(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Program", "", "JSON Files (*.json)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.steps = [Step(item["type"], item["params"]) for item in data]
            for step, item in zip(self.steps, data):
                step.active = item.get("active", True)
            self.refresh_joblist()

    def update_step_numbers(self):
        """Refresh the stored one-based step numbers after reordering."""
        for idx, step in enumerate(self.steps):
            step.number = idx + 1