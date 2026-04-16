"""Program step list and editing controls for the editor."""

import json
import os
from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from modules.polynomial_pressure import describe_pressure_function, is_open_loop_sensor, normalize_polynomial_pressure_params
from modules.program_contract import (
    PARAM_ACTION,
    PARAM_CONDITION,
    PARAM_CONTINUOUS,
    PARAM_DELTA_MBAR,
    PARAM_END_STEP,
    PARAM_FILENAME,
    PARAM_FILENAME_PREFIX,
    PARAM_INPUT_PRESSURE,
    PARAM_MAX_PRESSURE,
    PARAM_MIN_PRESSURE,
    PARAM_PORT,
    PARAM_PRESSURE,
    PARAM_REPETITIONS,
    PARAM_SENSOR,
    PARAM_STABLE_TIME,
    PARAM_START_STEP,
    PARAM_STATUS,
    PARAM_TARGET_FLOW,
    PARAM_TOLERANCE_PERCENT,
    PARAM_TIME_SEC,
    PARAM_TARGET_VALUE,
    PARAM_TARGET_VOLUME,
    PARAM_TOLERANCE,
    PARAM_VALVE_NAME,
    PARAM_WAIT,
    STEP_ADD_PRESSURE,
    STEP_CALIBRATE_WITH_FLUIGENT_SENSOR,
    STEP_DOSE_VOLUME,
    STEP_EXPORT_CSV,
    STEP_FLOW_CONTROLLER,
    STEP_LOAD_SEQUENCE,
    STEP_LOOP,
    STEP_PRESSURE_RAMP,
    STEP_POLYNOMIAL_PRESSURE,
    STEP_ROTARY_VALVE,
    STEP_SET_PRESSURE,
    STEP_START_MEASUREMENT,
    STEP_STOP_MEASUREMENT,
    STEP_VALVE,
    STEP_WAIT,
    STEP_WAIT_FOR_SENSOR_EVENT,
    STEP_ZERO_FLUIGENT,
    sampling_interval_ms_from_params,
)
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

            if step.type == STEP_FLOW_CONTROLLER:

                pid_button = QPushButton("\U0001F6E0")
                pid_button.setMaximumWidth(30)
                pid_button.clicked.connect(partial(self.edit_pid_parameters, step))
                item_layout.addWidget(pid_button)

            if step.type == STEP_VALVE:
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
        if step.type == STEP_SET_PRESSURE:
            pressure = step.params.get(PARAM_PRESSURE, 0.0)
            return f"Set Pressure ({pressure} mbar)"

        if step.type == STEP_ADD_PRESSURE:
            delta = step.params.get(PARAM_DELTA_MBAR, 0.0)
            return f"Add Pressure (+{delta} mbar)"

        if step.type == STEP_VALVE:
            valve_name = step.params.get(PARAM_VALVE_NAME, "Unknown")
            status = step.params.get(PARAM_STATUS, "Open")
            return f"Valve {valve_name} ({status})"

        if step.type == STEP_WAIT:
            time_sec = step.params.get(PARAM_TIME_SEC, 1.0)
            return f"Wait ({time_sec} s)"

        if step.type == STEP_WAIT_FOR_SENSOR_EVENT:
            sensor = step.params.get(PARAM_SENSOR, "Unknown")
            condition = step.params.get(PARAM_CONDITION, ">")
            target_value = step.params.get(PARAM_TARGET_VALUE, 0.0)
            tolerance = step.params.get(PARAM_TOLERANCE, 0.0)
            stable_time = step.params.get(PARAM_STABLE_TIME, 0.0)
            return f"Sensor {sensor} {condition} {target_value} (+/-{tolerance}, {stable_time}s)"

        if step.type == STEP_START_MEASUREMENT:
            interval_ms = sampling_interval_ms_from_params(step.params, default=250)
            return f"Start Measurement (Interval: {interval_ms} ms)"

        if step.type == STEP_STOP_MEASUREMENT:
            return "Stop Measurement"

        if step.type == STEP_EXPORT_CSV:
            prefix = step.params.get(PARAM_FILENAME_PREFIX, "Measurement")
            return f"Export CSV (Prefix: {prefix})"

        if step.type == STEP_PRESSURE_RAMP:
            return (
                f"Pressure Ramp ({step.params.get('start_pressure', 0.0)} -> "
                f"{step.params.get('end_pressure', 100.0)} mbar)"
            )

        if step.type == STEP_POLYNOMIAL_PRESSURE:
            cfg = normalize_polynomial_pressure_params(step.params)
            sensor_text = ""
            if not is_open_loop_sensor(cfg["sensor"]):
                sensor_text = f", sensor={cfg['sensor']}"
            return (
                f"PolynomialPressure ({describe_pressure_function(cfg)}, {cfg['duration']:g}s, "
                f"clamp {cfg['clamp_min']:g}..{cfg['clamp_max']:g} mbar, "
                f"slew {cfg['slew_limit']:g} mbar/s{sensor_text})"
            )
        if step.type == STEP_FLOW_CONTROLLER:
            target_flow = step.params.get(PARAM_TARGET_FLOW, 50.0)
            max_pressure = step.params.get(PARAM_MAX_PRESSURE, 350.0)
            min_pressure = step.params.get(PARAM_MIN_PRESSURE, 0.0)
            tolerance = step.params.get(PARAM_TOLERANCE_PERCENT, 10.0)
            continuous = "Continuous" if step.params.get(PARAM_CONTINUOUS, False) else "Stable"

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

        if step.type == STEP_ZERO_FLUIGENT:
            sensor_list = step.params.get("sensors", [])
            if not sensor_list:
                return "Zero Fluigent Sensors (All)"
            return f"Zero Fluigent Sensors ({', '.join(sensor_list)})"

        if step.type == STEP_CALIBRATE_WITH_FLUIGENT_SENSOR:
            sensor_name = step.params.get(PARAM_SENSOR, "Unknown")
            return f"Calibrate With {sensor_name}"

        if step.type == STEP_LOOP:
            start_step = step.params.get(PARAM_START_STEP, 1)
            end_step = step.params.get(PARAM_END_STEP, 1)
            repetitions = step.params.get(PARAM_REPETITIONS, 1)
            return f"Loop (Steps {start_step}-{end_step}, {repetitions}x)"

        if step.type == STEP_LOAD_SEQUENCE:
            filename = step.params.get(PARAM_FILENAME, "Unknown")
            return f"Load Sequence ({filename})"

        if step.type == STEP_DOSE_VOLUME:
            volume = step.params.get(PARAM_TARGET_VOLUME, 100.0)
            pneumatic_valve = step.params.get("pneumatic_valve", "?")
            fluidic_valve = step.params.get("fluidic_valve", "?")
            pressure = step.params.get(PARAM_INPUT_PRESSURE, "?")
            return f"Dose {volume} uL @ {pressure} mbar ({pneumatic_valve} -> {fluidic_valve})"

        if step.type == STEP_ROTARY_VALVE:
            action = step.params.get(PARAM_ACTION, "goto")
            if action == "goto":
                port = step.params.get(PARAM_PORT, 1)
                wait = step.params.get(PARAM_WAIT, True)
                return f"Rotary Valve (Goto {port}, wait={wait})"
            return f"Rotary Valve ({action})"

        return f"{step.type}"

    def toggle_active(self, step, state):
        step.active = (state == Qt.Checked)

    def toggle_valve(self, step):
        """Switch a valve step between Open and Close."""
        self.save_state()
        if step.type == STEP_VALVE:
            if step.params.get(PARAM_STATUS) == "Open":
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
        if step.type != STEP_FLOW_CONTROLLER:
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
