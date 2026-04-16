"""Editor dialogs for the special automation tasks."""

import os

from PyQt5.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from .task_globals import get_available_sensors


class SpecialTasks:
    """Configure pressure ramps, flow control, sequence loading, and calibration steps."""

    @staticmethod
    def get_all_task_names():
        """Return the special task names offered by the editor."""
        return [
            "Pressure Ramp",
            "Flow Controller",
            "Load Sequence",
            "Calibrate With Fluigent Sensor",
        ]

    @staticmethod
    def edit_task_params(parent, step):
        """Open the matching editor dialog for a special task."""
        if step.type == "Pressure Ramp":
            SpecialTasks.edit_pressure_ramp(parent, step)
        elif step.type == "Flow Controller":
            SpecialTasks.edit_flow_controller(parent, step)
        elif step.type == "Load Sequence":
            SpecialTasks.edit_load_sequence(parent, step)
        elif step.type == "Calibrate With Fluigent Sensor":
            SpecialTasks.edit_calibrate_from_fluigent(parent, step)

    @staticmethod
    def edit_pressure_ramp(parent, step):
        """Edit the parameters for an open-loop pressure ramp."""
        start_pressure, ok = QInputDialog.getDouble(
            parent, "Start Pressure", "Start Pressure [mbar]:", step.params.get("start_pressure", 0.0)
        )
        if not ok:
            return

        end_pressure, ok = QInputDialog.getDouble(
            parent, "End Pressure", "End Pressure [mbar]:", step.params.get("end_pressure", 100.0)
        )
        if not ok:
            return

        duration, ok = QInputDialog.getDouble(
            parent, "Duration", "Duration [s]:", step.params.get("duration", 10.0)
        )
        if not ok:
            return

        step.params = {
            "start_pressure": start_pressure,
            "end_pressure": end_pressure,
            "duration": duration,
        }

    @staticmethod
    def edit_flow_controller(parent, step):
        """Edit the PID-style flow controller parameters."""
        target_flow, ok = QInputDialog.getDouble(
            parent, "Target Flowrate", "Flowrate [uL/min]:", step.params.get("target_flow", 50.0)
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
            parent, "Max Pressure", "Maximum Pressure [mbar]:", step.params.get("max_pressure", 350.0)
        )
        if not ok:
            return

        min_pressure, ok = QInputDialog.getDouble(
            parent, "Min Pressure", "Minimum Pressure [mbar]:", step.params.get("min_pressure", 0.0)
        )
        if not ok:
            return

        tolerance_percent, ok = QInputDialog.getDouble(
            parent, "Tolerance (%)", "Allowed deviation from target:", step.params.get("tolerance_percent", 5.0)
        )
        if not ok:
            return

        stable_time, ok = QInputDialog.getDouble(
            parent, "Stable Time (s)", "Time for stable flow:", step.params.get("stable_time", 5.0)
        )
        if not ok:
            return

        continuous, ok = QInputDialog.getItem(
            parent, "Mode", "Control Mode:", ["Stable", "Continuous"], 0, False
        )
        if not ok:
            return

        step.params = {
            "target_flow": target_flow,
            "sensor": flow_sensor,
            "max_pressure": max_pressure,
            "min_pressure": min_pressure,
            "tolerance_percent": tolerance_percent,
            "stable_time": stable_time,
            "continuous": (continuous == "Continuous"),
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
                "filename": filename,
                "path": path,
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
            step.params = {"sensor": sensor_choice}
        else:
            QMessageBox.warning(parent, "No Sensor Selected", "Please select a sensor.")