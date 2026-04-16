"""Editor dialogs for the standard automation tasks."""

from PyQt5.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from modules.mf_common import select_item
from modules.program_contract import (
    CONDITION_STABLE,
    PARAM_ACTION,
    PARAM_CONDITION,
    PARAM_DELTA_MBAR,
    PARAM_END_STEP,
    PARAM_FILENAME_PREFIX,
    PARAM_FLOW_SENSOR,
    PARAM_FLUIDIC_VALVE,
    PARAM_FOLDER,
    PARAM_INPUT_PRESSURE,
    PARAM_PNEUMATIC_VALVE,
    PARAM_PORT,
    PARAM_PRESSURE,
    PARAM_REPETITIONS,
    PARAM_SAMPLING_INTERVAL_MS,
    PARAM_SENSOR,
    PARAM_SENSORS,
    PARAM_STABLE_TIME,
    PARAM_START_STEP,
    PARAM_STATUS,
    PARAM_TARGET_VALUE,
    PARAM_TARGET_VOLUME,
    PARAM_TIME_SEC,
    PARAM_TOLERANCE,
    PARAM_VALVE_NAME,
    PARAM_WAIT,
    ROTARY_ACTION_GOTO,
    ROTARY_ACTION_HOME,
    ROTARY_ACTION_NEXT,
    ROTARY_ACTION_PREV,
    STANDARD_STEP_NAMES,
    STATUS_CLOSE,
    STATUS_OPEN,
    STEP_ADD_PRESSURE,
    STEP_DOSE_VOLUME,
    STEP_EXPORT_CSV,
    STEP_LOOP,
    STEP_ROTARY_VALVE,
    STEP_SET_PRESSURE,
    STEP_START_MEASUREMENT,
    STEP_VALVE,
    STEP_WAIT,
    STEP_WAIT_FOR_SENSOR_EVENT,
    STEP_ZERO_FLUIGENT,
    sampling_interval_ms_from_params,
)

from .task_globals import get_available_sensors, get_available_valves


class EditorTasks:
    """Configure pressure, valve, wait, measurement, and utility steps."""

    @staticmethod
    def get_all_task_names():
        """Return the standard task names offered by the editor."""
        return list(STANDARD_STEP_NAMES)

    @staticmethod
    def edit_task_params(parent, step):
        """Open the matching editor dialog for a standard task."""
        if step.type == STEP_SET_PRESSURE:
            EditorTasks.edit_set_pressure(parent, step)
        elif step.type == STEP_ADD_PRESSURE:
            EditorTasks.edit_add_pressure(parent, step)
        elif step.type == STEP_VALVE:
            EditorTasks.edit_valve(parent, step)
        elif step.type == STEP_WAIT:
            EditorTasks.edit_wait(parent, step)
        elif step.type == STEP_WAIT_FOR_SENSOR_EVENT:
            EditorTasks.edit_sensor_event(parent, step)
        elif step.type == STEP_START_MEASUREMENT:
            EditorTasks.edit_start_measurement(parent, step)
        elif step.type == STEP_EXPORT_CSV:
            EditorTasks.edit_export_csv(parent, step)
        elif step.type == STEP_LOOP:
            EditorTasks.edit_loop_task(parent, step)
        elif step.type == STEP_DOSE_VOLUME:
            EditorTasks.edit_dose_volume(parent, step)
        elif step.type == STEP_ZERO_FLUIGENT:
            EditorTasks.edit_zero_fluigent(parent, step)
        elif step.type == STEP_ROTARY_VALVE:
            EditorTasks.edit_rotary_valve(parent, step)

    @staticmethod
    def edit_set_pressure(parent, step):
        """Edit the target pressure for a set-pressure step."""
        pressure, ok = QInputDialog.getDouble(
            parent, "Set Pressure", "Pressure [mbar]:", step.params.get(PARAM_PRESSURE, 100.0)
        )
        if ok:
            step.params = {PARAM_PRESSURE: pressure}

    @staticmethod
    def edit_valve(parent, step):
        """Choose the valve name and target state for a valve step."""
        valve_choices = get_available_valves()
        valve_name = select_item(parent, "Select Valve", "Valve:", valve_choices)
        if not valve_name:
            return

        status = select_item(parent, "Valve Status", "Status:", [STATUS_OPEN, STATUS_CLOSE])
        if not status:
            return

        step.params = {PARAM_VALVE_NAME: valve_name, PARAM_STATUS: status}

    @staticmethod
    def edit_wait(parent, step):
        """Edit the wait duration in seconds."""
        time_sec, ok = QInputDialog.getDouble(
            parent, "Wait Time", "Time [s]:", step.params.get(PARAM_TIME_SEC, 5.0)
        )
        if ok:
            step.params = {PARAM_TIME_SEC: time_sec}

    @staticmethod
    def edit_sensor_event(parent, step):
        """Edit the sensor condition, threshold, tolerance, and stability time."""
        sensor_choices = get_available_sensors()
        if not sensor_choices:
            QMessageBox.warning(parent, "No Sensors", "No sensors available.")
            return

        current_sensor = step.params.get("sensor", sensor_choices[0] if sensor_choices else "")
        sensor, ok = QInputDialog.getItem(
            parent,
            "Sensor",
            "Sensor name:",
            sensor_choices,
            max(0, sensor_choices.index(current_sensor)) if current_sensor in sensor_choices else 0,
            False,
        )
        if not ok:
            return

        valid_conditions = [">", "<", "=", CONDITION_STABLE]
        current_cond = step.params.get("condition", valid_conditions[0])
        condition, ok = QInputDialog.getItem(
            parent,
            "Condition",
            "Condition:",
            valid_conditions,
            max(0, valid_conditions.index(current_cond)) if current_cond in valid_conditions else 0,
            False,
        )
        if not ok:
            return

        target_value = float(step.params.get(PARAM_TARGET_VALUE, 0.0))
        if condition != CONDITION_STABLE:
            target_value, ok = QInputDialog.getDouble(
                parent, "Target Value", "Target value:", target_value
            )
            if not ok:
                return

        tolerance = float(step.params.get(PARAM_TOLERANCE, 1.0))
        tolerance, ok = QInputDialog.getDouble(
            parent, "Tolerance (+/-)", "Tolerance value:", tolerance
        )
        if not ok:
            return

        stable_time = float(step.params.get(PARAM_STABLE_TIME, 5.0))
        stable_time, ok = QInputDialog.getDouble(
            parent, "Stability Time (s)", "Time for stability:", stable_time
        )
        if not ok:
            return

        step.params = {
            PARAM_SENSOR: sensor,
            PARAM_CONDITION: condition,
            PARAM_TARGET_VALUE: target_value,
            PARAM_TOLERANCE: tolerance,
            PARAM_STABLE_TIME: stable_time,
        }

    @staticmethod
    def edit_start_measurement(parent, step):
        """Edit the measurement sampling interval in milliseconds."""
        interval_ms = sampling_interval_ms_from_params(step.params, default=250)

        interval_ms, ok = QInputDialog.getInt(
            parent, "Sampling Interval", "Interval [ms]:", interval_ms, 1
        )
        if ok:
            step.params = {PARAM_SAMPLING_INTERVAL_MS: interval_ms}

    @staticmethod
    def edit_export_csv(parent, step):
        """Choose the export filename prefix and destination folder."""
        filename_prefix, ok = QInputDialog.getText(
            parent, "Filename Prefix", "Prefix:", text=step.params.get(PARAM_FILENAME_PREFIX, "Measurement")
        )
        if not ok:
            return

        folder = QFileDialog.getExistingDirectory(parent, "Select Export Folder")
        if not folder:
            return

        step.params = {
            PARAM_FILENAME_PREFIX: filename_prefix,
            PARAM_FOLDER: folder,
        }

    @staticmethod
    def edit_loop_task(parent, step):
        """Edit the start step, end step, and repetition count for a loop."""
        start_step, ok = QInputDialog.getInt(
            parent, "Start Step", "Enter start step number:", step.params.get(PARAM_START_STEP, 1)
        )
        if not ok:
            return

        end_step, ok = QInputDialog.getInt(
            parent, "End Step", "Enter end step number:", step.params.get(PARAM_END_STEP, start_step)
        )
        if not ok:
            return

        if end_step < start_step:
            QMessageBox.warning(parent, "Invalid Range", "End step must be greater than or equal to start step.")
            return

        repetitions, ok = QInputDialog.getInt(
            parent, "Repetitions", "Number of times to repeat:", step.params.get(PARAM_REPETITIONS, 3)
        )
        if not ok:
            return

        if repetitions < 1:
            QMessageBox.warning(parent, "Invalid Repetitions", "Repetitions must be at least 1.")
            return

        step.params = {
            PARAM_START_STEP: start_step,
            PARAM_END_STEP: end_step,
            PARAM_REPETITIONS: repetitions,
        }

    @staticmethod
    def edit_dose_volume(parent, step):
        """Edit the flow sensor, valves, target volume, and dosing pressure."""
        sensor_choices = get_available_sensors()
        flow_sensor_choices = [s for s in sensor_choices if "Flow" in s]
        flow_sensor, ok = QInputDialog.getItem(parent, "Flow Sensor", "Sensor:", flow_sensor_choices, 0, False)
        if not ok:
            return

        valve_choices = get_available_valves()
        pneumatic_valves = [v for v in valve_choices if "Pneumatic" in v]
        fluidic_valves = [v for v in valve_choices if "Fluidic" in v]

        pneumatic_valve, ok = QInputDialog.getItem(parent, "Pneumatic Valve", "Valve:", pneumatic_valves, 0, False)
        if not ok:
            return

        fluidic_valve, ok = QInputDialog.getItem(parent, "Fluidic Valve", "Valve:", fluidic_valves, 0, False)
        if not ok:
            return

        target_volume, ok = QInputDialog.getDouble(
            parent,
            "Target Volume",
            "Volume to dose [uL]:",
            step.params.get(PARAM_TARGET_VOLUME, 100.0),
            0.1,
            100000.0,
            1,
        )
        if not ok:
            return

        input_pressure, ok = QInputDialog.getDouble(
            parent,
            "Input Pressure",
            "Dosing pressure [mbar]:",
            step.params.get(PARAM_INPUT_PRESSURE, 200.0),
            0.0,
            1000.0,
            1,
        )
        if not ok:
            return

        step.params = {
            PARAM_FLOW_SENSOR: flow_sensor,
            PARAM_PNEUMATIC_VALVE: pneumatic_valve,
            PARAM_FLUIDIC_VALVE: fluidic_valve,
            PARAM_TARGET_VOLUME: target_volume,
            PARAM_INPUT_PRESSURE: input_pressure,
        }

    @staticmethod
    def edit_zero_fluigent(parent, step):
        """Choose one Fluigent sensor or leave the step as an all-sensors reset."""
        sensor_choices = [s for s in get_available_sensors() if s.startswith("SN")]
        sensor_choices.insert(0, "All")

        selected, ok = QInputDialog.getItem(
            parent, "Zero Fluigent Sensor(s)", "Sensor:", sensor_choices, 0, False
        )
        if not ok:
            return

        if selected == "All":
            step.params = {PARAM_SENSORS: []}
        else:
            step.params = {PARAM_SENSORS: [selected]}

    @staticmethod
    def edit_rotary_valve(parent, step):
        """Configure the action, target port, and wait behavior for a rotary valve step."""
        action, ok = QInputDialog.getItem(
            parent, "Rotary Valve Action", "Action:", [ROTARY_ACTION_GOTO, ROTARY_ACTION_HOME, ROTARY_ACTION_PREV, ROTARY_ACTION_NEXT], 0, False
        )
        if not ok:
            return

        params = {PARAM_ACTION: action}
        wait_default = True

        if action == ROTARY_ACTION_GOTO:
            port, ok = QInputDialog.getInt(
                parent,
                "Goto Port",
                "Port (1..12):",
                step.params.get(PARAM_PORT, 1),
                1,
                12,
                1,
            )
            if not ok:
                return
            params[PARAM_PORT] = port

        wait_str, ok = QInputDialog.getItem(
            parent,
            "Wait for completion?",
            "Wait:",
            ["True", "False"],
            0 if step.params.get(PARAM_WAIT, wait_default) else 1,
            False,
        )
        if not ok:
            return

        params[PARAM_WAIT] = (wait_str == "True")
        step.params = params

    @staticmethod
    def edit_add_pressure(parent, step):
        """Edit the pressure delta for an add-pressure step."""
        delta, ok = QInputDialog.getDouble(
            parent,
            "Add Pressure",
            "Delta Pressure [mbar]:",
            step.params.get(PARAM_DELTA_MBAR, 10.0),
        )
        if ok:
            step.params = {PARAM_DELTA_MBAR: delta}