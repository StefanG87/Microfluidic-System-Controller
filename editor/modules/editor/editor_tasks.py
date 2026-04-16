"""Editor dialogs for the standard automation tasks."""

from PyQt5.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from modules.mf_common import select_item

from .task_globals import get_available_sensors, get_available_valves


class EditorTasks:
    """Configure pressure, valve, wait, measurement, and utility steps."""

    @staticmethod
    def get_all_task_names():
        """Return the standard task names offered by the editor."""
        return [
            "Set Pressure",
            "Set Pressure to 0",
            "Add Pressure",
            "Valve",
            "Wait",
            "Wait for Sensor Event",
            "Start Measurement",
            "Export CSV",
            "ZeroFluigent",
            "Loop",
            "Dose Volume",
            "Rotary Valve",
        ]

    @staticmethod
    def edit_task_params(parent, step):
        """Open the matching editor dialog for a standard task."""
        if step.type == "Set Pressure":
            EditorTasks.edit_set_pressure(parent, step)
        elif step.type == "Add Pressure":
            EditorTasks.edit_add_pressure(parent, step)
        elif step.type == "Valve":
            EditorTasks.edit_valve(parent, step)
        elif step.type == "Wait":
            EditorTasks.edit_wait(parent, step)
        elif step.type == "Wait for Sensor Event":
            EditorTasks.edit_sensor_event(parent, step)
        elif step.type == "Start Measurement":
            EditorTasks.edit_start_measurement(parent, step)
        elif step.type == "Export CSV":
            EditorTasks.edit_export_csv(parent, step)
        elif step.type == "Loop":
            EditorTasks.edit_loop_task(parent, step)
        elif step.type == "Dose Volume":
            EditorTasks.edit_dose_volume(parent, step)
        elif step.type == "ZeroFluigent":
            EditorTasks.edit_zero_fluigent(parent, step)
        elif step.type == "Rotary Valve":
            EditorTasks.edit_rotary_valve(parent, step)

    @staticmethod
    def edit_set_pressure(parent, step):
        """Edit the target pressure for a set-pressure step."""
        pressure, ok = QInputDialog.getDouble(
            parent, "Set Pressure", "Pressure [mbar]:", step.params.get("pressure", 100.0)
        )
        if ok:
            step.params = {"pressure": pressure}

    @staticmethod
    def edit_valve(parent, step):
        """Choose the valve name and target state for a valve step."""
        valve_choices = get_available_valves()
        valve_name = select_item(parent, "Select Valve", "Valve:", valve_choices)
        if not valve_name:
            return

        status = select_item(parent, "Valve Status", "Status:", ["Open", "Close"])
        if not status:
            return

        step.params = {"valve_name": valve_name, "status": status}

    @staticmethod
    def edit_wait(parent, step):
        """Edit the wait duration in seconds."""
        time_sec, ok = QInputDialog.getDouble(
            parent, "Wait Time", "Time [s]:", step.params.get("time_sec", 5.0)
        )
        if ok:
            step.params = {"time_sec": time_sec}

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

        valid_conditions = [">", "<", "=", "Stable"]
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

        target_value = float(step.params.get("target_value", 0.0))
        if condition != "Stable":
            target_value, ok = QInputDialog.getDouble(
                parent, "Target Value", "Target value:", target_value
            )
            if not ok:
                return

        tolerance = float(step.params.get("tolerance", 1.0))
        tolerance, ok = QInputDialog.getDouble(
            parent, "Tolerance (+/-)", "Tolerance value:", tolerance
        )
        if not ok:
            return

        stable_time = float(step.params.get("stable_time", 5.0))
        stable_time, ok = QInputDialog.getDouble(
            parent, "Stability Time (s)", "Time for stability:", stable_time
        )
        if not ok:
            return

        step.params = {
            "sensor": sensor,
            "condition": condition,
            "target_value": target_value,
            "tolerance": tolerance,
            "stable_time": stable_time,
        }

    @staticmethod
    def edit_start_measurement(parent, step):
        """Edit the requested measurement sampling rate in hertz."""
        sampling_rate, ok = QInputDialog.getDouble(
            parent, "Sampling Rate", "Rate [Hz]:", step.params.get("sampling_rate", 10)
        )
        if ok:
            step.params = {"sampling_rate": sampling_rate}

    @staticmethod
    def edit_export_csv(parent, step):
        """Choose the export filename prefix and destination folder."""
        filename_prefix, ok = QInputDialog.getText(
            parent, "Filename Prefix", "Prefix:", text=step.params.get("filename_prefix", "Measurement")
        )
        if not ok:
            return

        folder = QFileDialog.getExistingDirectory(parent, "Select Export Folder")
        if not folder:
            return

        step.params = {
            "filename_prefix": filename_prefix,
            "folder": folder,
        }

    @staticmethod
    def edit_loop_task(parent, step):
        """Edit the start step, end step, and repetition count for a loop."""
        start_step, ok = QInputDialog.getInt(
            parent, "Start Step", "Enter start step number:", step.params.get("start_step", 1)
        )
        if not ok:
            return

        end_step, ok = QInputDialog.getInt(
            parent, "End Step", "Enter end step number:", step.params.get("end_step", start_step)
        )
        if not ok:
            return

        if end_step < start_step:
            QMessageBox.warning(parent, "Invalid Range", "End step must be greater than or equal to start step.")
            return

        repetitions, ok = QInputDialog.getInt(
            parent, "Repetitions", "Number of times to repeat:", step.params.get("repetitions", 3)
        )
        if not ok:
            return

        if repetitions < 1:
            QMessageBox.warning(parent, "Invalid Repetitions", "Repetitions must be at least 1.")
            return

        step.params = {
            "start_step": start_step,
            "end_step": end_step,
            "repetitions": repetitions,
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
            step.params.get("target_volume", 100.0),
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
            step.params.get("input_pressure", 200.0),
            0.0,
            1000.0,
            1,
        )
        if not ok:
            return

        step.params = {
            "flow_sensor": flow_sensor,
            "pneumatic_valve": pneumatic_valve,
            "fluidic_valve": fluidic_valve,
            "target_volume": target_volume,
            "input_pressure": input_pressure,
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
            step.params = {"sensors": []}
        else:
            step.params = {"sensors": [selected]}

    @staticmethod
    def edit_rotary_valve(parent, step):
        """Configure the action, target port, and wait behavior for a rotary valve step."""
        action, ok = QInputDialog.getItem(
            parent, "Rotary Valve Action", "Action:", ["goto", "home", "prev", "next"], 0, False
        )
        if not ok:
            return

        params = {"action": action}
        wait_default = True

        if action == "goto":
            port, ok = QInputDialog.getInt(
                parent,
                "Goto Port",
                "Port (1..12):",
                step.params.get("port", 1),
                1,
                12,
                1,
            )
            if not ok:
                return
            params["port"] = port

        wait_str, ok = QInputDialog.getItem(
            parent,
            "Wait for completion?",
            "Wait:",
            ["True", "False"],
            0 if step.params.get("wait", wait_default) else 1,
            False,
        )
        if not ok:
            return

        params["wait"] = (wait_str == "True")
        step.params = params

    @staticmethod
    def edit_add_pressure(parent, step):
        """Edit the pressure delta for an add-pressure step."""
        delta, ok = QInputDialog.getDouble(
            parent,
            "Add Pressure",
            "Delta Pressure [mbar]:",
            step.params.get("delta_mbar", 10.0),
        )
        if ok:
            step.params = {"delta_mbar": delta}