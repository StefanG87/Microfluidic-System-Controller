"""Editor dialogs for the special automation tasks."""

import os

from PyQt5.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from modules.program_contract import (
    PARAM_CONTINUOUS,
    PARAM_DURATION,
    PARAM_END_PRESSURE,
    PARAM_FILENAME,
    PARAM_MAX_PRESSURE,
    PARAM_MIN_PRESSURE,
    PARAM_PATH,
    PARAM_SENSOR,
    PARAM_STABLE_TIME,
    PARAM_START_PRESSURE,
    PARAM_TARGET_FLOW,
    PARAM_TOLERANCE_PERCENT,
    SPECIAL_STEP_NAMES,
    STEP_CALIBRATE_WITH_FLUIGENT_SENSOR,
    STEP_FLOW_CONTROLLER,
    STEP_LOAD_SEQUENCE,
    STEP_PRESSURE_RAMP,
)

from .task_globals import get_available_sensors


class SpecialTasks:
    """Configure pressure ramps, flow control, sequence loading, and calibration steps."""

    @staticmethod
    def get_all_task_names():
        """Return the special task names offered by the editor."""
        return list(SPECIAL_STEP_NAMES)

    @staticmethod
    def edit_task_params(parent, step):
        """Open the matching editor dialog for a special task."""
        if step.type == STEP_PRESSURE_RAMP:
            SpecialTasks.edit_pressure_ramp(parent, step)
        elif step.type == STEP_FLOW_CONTROLLER:
            SpecialTasks.edit_flow_controller(parent, step)
        elif step.type == STEP_LOAD_SEQUENCE:
            SpecialTasks.edit_load_sequence(parent, step)
        elif step.type == STEP_CALIBRATE_WITH_FLUIGENT_SENSOR:
            SpecialTasks.edit_calibrate_from_fluigent(parent, step)

    @staticmethod
    def edit_pressure_ramp(parent, step):
        """Edit the parameters for an open-loop pressure ramp."""
        start_pressure, ok = QInputDialog.getDouble(
            parent, "Start Pressure", "Start Pressure [mbar]:", step.params.get(PARAM_START_PRESSURE, 0.0)
        )
        if not ok:
            return

        end_pressure, ok = QInputDialog.getDouble(
            parent, "End Pressure", "End Pressure [mbar]:", step.params.get(PARAM_END_PRESSURE, 100.0)
        )
        if not ok:
            return

        duration, ok = QInputDialog.getDouble(
            parent, "Duration", "Duration [s]:", step.params.get(PARAM_DURATION, 10.0)
        )
        if not ok:
            return

        step.params = {
            PARAM_START_PRESSURE: start_pressure,
            PARAM_END_PRESSURE: end_pressure,
            PARAM_DURATION: duration,
        }

    @staticmethod
    def edit_flow_controller(parent, step):
        """Edit the PID-style flow controller parameters."""
        target_flow, ok = QInputDialog.getDouble(
            parent, "Target Flowrate", "Flowrate [uL/min]:", step.params.get(PARAM_TARGET_FLOW, 50.0)
        )
        if not ok:
            return

        sensor_choices = [s for s in get_available_sensors() if "Flow" in s] or ["Flow 1", "Flow 2", "Flow 3"]
        flow_sensor, ok = QInputDialog.getItem(
            parent, "Flow Sensor", "Select Sensor:", sensor_choices, 0, False
        )
        if not ok:
            return

        max_pressure, ok = QInputDialog.getDouble(
            parent, "Max Pressure", "Maximum Pressure [mbar]:", step.params.get(PARAM_MAX_PRESSURE, 350.0)
        )
        if not ok:
            return

        min_pressure, ok = QInputDialog.getDouble(
            parent, "Min Pressure", "Minimum Pressure [mbar]:", step.params.get(PARAM_MIN_PRESSURE, 0.0)
        )
        if not ok:
            return

        tolerance_percent, ok = QInputDialog.getDouble(
            parent, "Tolerance (%)", "Allowed deviation from target:", step.params.get(PARAM_TOLERANCE_PERCENT, 5.0)
        )
        if not ok:
            return

        stable_time, ok = QInputDialog.getDouble(
            parent, "Stable Time (s)", "Time for stable flow:", step.params.get(PARAM_STABLE_TIME, 5.0)
        )
        if not ok:
            return

        continuous, ok = QInputDialog.getItem(
            parent, "Mode", "Control Mode:", ["Stable", "Continuous"], 0, False
        )
        if not ok:
            return

        step.params = {
            PARAM_TARGET_FLOW: target_flow,
            PARAM_SENSOR: flow_sensor,
            PARAM_MAX_PRESSURE: max_pressure,
            PARAM_MIN_PRESSURE: min_pressure,
            PARAM_TOLERANCE_PERCENT: tolerance_percent,
            PARAM_STABLE_TIME: stable_time,
            PARAM_CONTINUOUS: (continuous == "Continuous"),
        }

    @staticmethod
    def edit_load_sequence(parent, step):
        """Select a saved JSON sequence file and store its basename and path."""
        path, _ = QFileDialog.getOpenFileName(
            parent,
            "Select Sequence File",
            "",
            "JSON Files (*.json)",
        )
        if path:
            filename = os.path.basename(path)
            step.params = {
                PARAM_FILENAME: filename,
                PARAM_PATH: path,
            }

    @staticmethod
    def edit_zero_fluigent(parent, step):
        """Keep the step parameterless; zeroing happens when the program runs."""
        step.params = {}

    @staticmethod
    def edit_calibrate_from_fluigent(parent, step):
        """Select the Fluigent sensor used for pressure calibration."""
        fluigent_sensors = [s for s in get_available_sensors() if s.startswith("SN")]
        if not fluigent_sensors:
            QMessageBox.warning(parent, "No Sensors", "No Fluigent sensors available.")
            return

        sensor_choice, ok = QInputDialog.getItem(
            parent, "Select Fluigent Sensor", "Sensor:", fluigent_sensors, 0, False
        )
        if ok and sensor_choice:
            step.params = {PARAM_SENSOR: sensor_choice}
        else:
            QMessageBox.warning(parent, "No Sensor Selected", "Please select a sensor.")
