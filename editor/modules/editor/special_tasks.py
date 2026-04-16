"""Editor dialogs for the special automation tasks."""

import os

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from modules.polynomial_pressure import (
    CONTROL_SENSOR_OPEN_LOOP,
    DEFAULT_CLAMP_MAX_MBAR,
    DEFAULT_CLAMP_MIN_MBAR,
    DEFAULT_FEEDBACK_GAIN,
    DEFAULT_MAX_CORRECTION_MBAR,
    DEFAULT_SAMPLE_INTERVAL_S,
    DEFAULT_SLEW_LIMIT_MBAR_PER_S,
    MAX_POLYNOMIAL_ORDER,
    build_pressure_profile,
    describe_pressure_function,
    is_open_loop_sensor,
    normalize_polynomial_pressure_params,
)
from modules.program_contract import (
    PARAM_AMPLITUDE_MBAR,
    PARAM_CLAMP_MAX,
    PARAM_CLAMP_MIN,
    PARAM_CONTINUOUS,
    PARAM_COEFFICIENTS,
    PARAM_DURATION,
    PARAM_END_PRESSURE,
    PARAM_FEEDBACK_GAIN,
    PARAM_FILENAME,
    PARAM_MAX_CORRECTION,
    PARAM_MAX_PRESSURE,
    PARAM_MIN_PRESSURE,
    PARAM_MODE,
    PARAM_OFFSET_MBAR,
    PARAM_ORDER,
    PARAM_PATH,
    PARAM_PERIOD_S,
    PARAM_PHASE_DEG,
    PARAM_SAMPLE_INTERVAL,
    PARAM_SENSOR,
    PARAM_SLEW_LIMIT,
    PARAM_STABLE_TIME,
    PARAM_START_PRESSURE,
    PARAM_TARGET_FLOW,
    PARAM_TOLERANCE_PERCENT,
    SPECIAL_STEP_NAMES,
    STEP_CALIBRATE_WITH_FLUIGENT_SENSOR,
    STEP_FLOW_CONTROLLER,
    STEP_LOAD_SEQUENCE,
    STEP_PRESSURE_RAMP,
    STEP_POLYNOMIAL_PRESSURE,
)

from .task_globals import get_available_sensors


class PolynomialPressureDialog(QDialog):
    """Configure a time-dependent pressure setpoint with live preview."""

    def __init__(self, parent=None, params=None):
        super().__init__(parent)
        self.setWindowTitle("PolynomialPressure")
        self.setMinimumWidth(800)

        cfg = normalize_polynomial_pressure_params(params or {})
        coeffs = list(cfg["coefficients"])
        while len(coeffs) <= MAX_POLYNOMIAL_ORDER:
            coeffs.append(0.0)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Linear: P(t) = m*t + n", "linear")
        self.mode_combo.addItem("Quadratic: P(t) = a*t^2 + m*t + n", "quadratic")
        self.mode_combo.addItem("Cubic: P(t) = b*t^3 + a*t^2 + m*t + n", "cubic")
        self.mode_combo.addItem("Polynomial: c0 + c1*t + ...", "polynomial")
        self.mode_combo.addItem("Sine: offset + amplitude*sin(...) ", "sine")
        self._set_combo_value(self.mode_combo, cfg["mode"])
        form.addRow("Function:", self.mode_combo)

        self.order_label = QLabel("Order:")
        self.order_spin = QSpinBox()
        self.order_spin.setRange(0, MAX_POLYNOMIAL_ORDER)
        self.order_spin.setValue(max(0, min(MAX_POLYNOMIAL_ORDER, cfg["order"])))
        form.addRow(self.order_label, self.order_spin)

        self.duration_spin = self._make_spin(cfg["duration"], 0.1, 86400.0, 2, 1.0, " s")
        form.addRow("Duration:", self.duration_spin)

        self.coeff_labels = []
        self.coeff_spins = []
        for power in range(MAX_POLYNOMIAL_ORDER + 1):
            label = QLabel(self._coefficient_label(power))
            spin = self._make_spin(coeffs[power], -100000.0, 100000.0, 6, 0.1, "")
            self.coeff_labels.append(label)
            self.coeff_spins.append(spin)
            form.addRow(label, spin)

        self.offset_label = QLabel("Offset [mbar]:")
        self.offset_spin = self._make_spin(cfg["offset_mbar"], -10000.0, 10000.0, 3, 1.0, "")
        form.addRow(self.offset_label, self.offset_spin)

        self.amplitude_label = QLabel("Amplitude [mbar]:")
        self.amplitude_spin = self._make_spin(cfg["amplitude_mbar"], -10000.0, 10000.0, 3, 1.0, "")
        form.addRow(self.amplitude_label, self.amplitude_spin)

        self.period_label = QLabel("Period [s]:")
        self.period_spin = self._make_spin(cfg["period_s"], 0.001, 86400.0, 3, 1.0, " s")
        form.addRow(self.period_label, self.period_spin)

        self.phase_label = QLabel("Phase [deg]:")
        self.phase_spin = self._make_spin(cfg["phase_deg"], -3600.0, 3600.0, 2, 15.0, " deg")
        form.addRow(self.phase_label, self.phase_spin)

        self.clamp_min_spin = self._make_spin(cfg["clamp_min"], -1000.0, 5000.0, 2, 10.0, " mbar")
        form.addRow("Clamp min:", self.clamp_min_spin)

        self.clamp_max_spin = self._make_spin(cfg["clamp_max"], -1000.0, 5000.0, 2, 10.0, " mbar")
        form.addRow("Clamp max:", self.clamp_max_spin)

        self.slew_spin = self._make_spin(cfg["slew_limit"], 0.0, 10000.0, 2, 10.0, " mbar/s")
        form.addRow("Slew limit:", self.slew_spin)

        self.sample_interval_spin = self._make_spin(cfg["sample_interval"], 0.01, 60.0, 3, 0.05, " s")
        form.addRow("Update interval:", self.sample_interval_spin)

        self.sensor_combo = QComboBox()
        for sensor in self._pressure_sensor_choices(cfg["sensor"]):
            self.sensor_combo.addItem(sensor, sensor)
        self._set_combo_value(self.sensor_combo, cfg["sensor"])
        form.addRow("Pressure sensor:", self.sensor_combo)

        self.feedback_gain_label = QLabel("Feedback Kp:")
        self.feedback_gain_spin = self._make_spin(cfg["feedback_gain"], 0.0, 100.0, 4, 0.1, "")
        form.addRow(self.feedback_gain_label, self.feedback_gain_spin)

        self.max_correction_label = QLabel("Max correction:")
        self.max_correction_spin = self._make_spin(cfg["max_correction"], 0.0, 5000.0, 2, 10.0, " mbar")
        form.addRow(self.max_correction_label, self.max_correction_spin)

        self.figure = Figure(figsize=(7.0, 3.4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        layout.addWidget(self.canvas)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.mode_combo.currentIndexChanged.connect(self._on_input_changed)
        self.order_spin.valueChanged.connect(self._on_input_changed)
        self.duration_spin.valueChanged.connect(self._on_input_changed)
        for spin in self.coeff_spins:
            spin.valueChanged.connect(self._on_input_changed)
        self.offset_spin.valueChanged.connect(self._on_input_changed)
        self.amplitude_spin.valueChanged.connect(self._on_input_changed)
        self.period_spin.valueChanged.connect(self._on_input_changed)
        self.phase_spin.valueChanged.connect(self._on_input_changed)
        self.clamp_min_spin.valueChanged.connect(self._on_input_changed)
        self.clamp_max_spin.valueChanged.connect(self._on_input_changed)
        self.slew_spin.valueChanged.connect(self._on_input_changed)
        self.sample_interval_spin.valueChanged.connect(self._on_input_changed)
        self.sensor_combo.currentIndexChanged.connect(self._on_input_changed)
        self.feedback_gain_spin.valueChanged.connect(self._on_input_changed)
        self.max_correction_spin.valueChanged.connect(self._on_input_changed)

        self._on_input_changed()

    @staticmethod
    def _make_spin(value, minimum, maximum, decimals, step, suffix):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setValue(float(value))
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(True)
        return spin

    @staticmethod
    def _set_combo_value(combo, value):
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        if value:
            combo.addItem(str(value), str(value))
            combo.setCurrentIndex(combo.count() - 1)

    @staticmethod
    def _coefficient_label(power):
        if power == 0:
            return "c0 / n [mbar]:"
        if power == 1:
            return "c1 / m [mbar/s]:"
        return f"c{power} [mbar/s^{power}]:"

    @staticmethod
    def _pressure_sensor_choices(current_sensor):
        choices = [CONTROL_SENSOR_OPEN_LOOP, "Internal"]
        choices.extend(s for s in get_available_sensors() if str(s).startswith("SN"))
        if current_sensor and current_sensor not in choices:
            choices.append(str(current_sensor))
        return choices

    def _active_order(self):
        mode = self.mode_combo.currentData()
        if mode == "linear":
            return 1
        if mode == "quadratic":
            return 2
        if mode == "cubic":
            return 3
        if mode == "polynomial":
            return int(self.order_spin.value())
        return 0

    def _on_input_changed(self):
        mode = self.mode_combo.currentData()
        is_sine = mode == "sine"
        is_free_poly = mode == "polynomial"
        order = self._active_order()

        self.order_label.setVisible(is_free_poly)
        self.order_spin.setVisible(is_free_poly)

        for power, (label, spin) in enumerate(zip(self.coeff_labels, self.coeff_spins)):
            visible = (not is_sine) and power <= order
            label.setVisible(visible)
            spin.setVisible(visible)

        for widget in (
            self.offset_label,
            self.offset_spin,
            self.amplitude_label,
            self.amplitude_spin,
            self.period_label,
            self.period_spin,
            self.phase_label,
            self.phase_spin,
        ):
            widget.setVisible(is_sine)

        closed_loop = not is_open_loop_sensor(self.sensor_combo.currentText())
        self.feedback_gain_label.setVisible(closed_loop)
        self.feedback_gain_spin.setVisible(closed_loop)
        self.max_correction_label.setVisible(closed_loop)
        self.max_correction_spin.setVisible(closed_loop)

        self.update_preview()

    def to_params(self):
        mode = self.mode_combo.currentData()
        order = self._active_order()
        params = {
            PARAM_MODE: mode,
            PARAM_ORDER: order,
            PARAM_DURATION: self.duration_spin.value(),
            PARAM_CLAMP_MIN: self.clamp_min_spin.value(),
            PARAM_CLAMP_MAX: self.clamp_max_spin.value(),
            PARAM_SLEW_LIMIT: self.slew_spin.value(),
            PARAM_SAMPLE_INTERVAL: self.sample_interval_spin.value(),
            PARAM_SENSOR: self.sensor_combo.currentText(),
            PARAM_FEEDBACK_GAIN: self.feedback_gain_spin.value(),
            PARAM_MAX_CORRECTION: self.max_correction_spin.value(),
        }

        if mode == "sine":
            params.update(
                {
                    PARAM_OFFSET_MBAR: self.offset_spin.value(),
                    PARAM_AMPLITUDE_MBAR: self.amplitude_spin.value(),
                    PARAM_PERIOD_S: self.period_spin.value(),
                    PARAM_PHASE_DEG: self.phase_spin.value(),
                }
            )
        else:
            coefficients = [self.coeff_spins[i].value() for i in range(order + 1)]
            params[PARAM_COEFFICIENTS] = coefficients
            if order >= 1:
                params["m_mbar_per_s"] = coefficients[1]
            params["n_mbar"] = coefficients[0]
            if order >= 2:
                params["a_mbar_per_s2"] = coefficients[2]
            if order >= 3:
                params["b_mbar_per_s3"] = coefficients[3]
        return params

    def update_preview(self):
        params = self.to_params()
        preview_interval = max(0.02, params[PARAM_DURATION] / 240.0)
        points = build_pressure_profile(params, sample_interval=preview_interval)
        times = [p["time"] for p in points]
        raw = [p["raw"] for p in points]
        clamped = [p["clamped"] for p in points]
        limited = [p["limited"] for p in points]

        self.ax.clear()
        self.ax.plot(times, raw, color="0.55", linestyle="--", label="Raw")
        self.ax.plot(times, clamped, color="tab:orange", linestyle=":", label="Clamped")
        self.ax.plot(times, limited, color="tab:blue", label="Applied target")
        self.ax.set_xlabel("Time [s]")
        self.ax.set_ylabel("Pressure [mbar]")
        self.ax.set_xlim(0.0, max(1.0, params[PARAM_DURATION]))
        y_values = raw + clamped + limited + [params[PARAM_CLAMP_MIN], params[PARAM_CLAMP_MAX]]
        y_min = min(y_values)
        y_max = max(y_values)
        pad = max(5.0, 0.08 * max(1.0, y_max - y_min))
        self.ax.set_ylim(y_min - pad, y_max + pad)
        self.ax.grid(True, linestyle=":", linewidth=0.5)
        self.ax.legend(loc="best", frameon=False)
        self.canvas.draw_idle()

        max_rate = 0.0
        for idx in range(1, len(points)):
            dt = points[idx]["time"] - points[idx - 1]["time"]
            if dt > 0:
                max_rate = max(max_rate, abs(limited[idx] - limited[idx - 1]) / dt)

        cfg = normalize_polynomial_pressure_params(params)
        sensor_text = "open-loop actuator setpoint"
        if not is_open_loop_sensor(cfg["sensor"]):
            sensor_text = f"closed-loop on {cfg['sensor']} (Kp={cfg['feedback_gain']:g}, max correction={cfg['max_correction']:g} mbar)"
        self.summary_label.setText(
            f"{describe_pressure_function(cfg)} | Applied target: min {min(limited):.2f} mbar, "
            f"max {max(limited):.2f} mbar, end {limited[-1]:.2f} mbar, "
            f"max dP/dt {max_rate:.2f} mbar/s | {sensor_text}"
        )

    def accept(self):
        if self.duration_spin.value() <= 0.0:
            QMessageBox.warning(self, "Invalid Duration", "Duration must be greater than 0 s.")
            return
        if self.clamp_max_spin.value() <= self.clamp_min_spin.value():
            QMessageBox.warning(self, "Invalid Clamp", "Clamp max must be greater than clamp min.")
            return
        if self.mode_combo.currentData() == "sine" and self.period_spin.value() <= 0.0:
            QMessageBox.warning(self, "Invalid Period", "Sine period must be greater than 0 s.")
            return
        super().accept()


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
        elif step.type == STEP_POLYNOMIAL_PRESSURE:
            SpecialTasks.edit_polynomial_pressure(parent, step)
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
    def edit_polynomial_pressure(parent, step):
        """Edit a PolynomialPressure step with a live curve preview."""
        dialog = PolynomialPressureDialog(parent, step.params)
        if dialog.exec_() == QDialog.Accepted:
            step.params = dialog.to_params()

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
