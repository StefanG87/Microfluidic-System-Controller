"""Task-specific PySide6 parameter dialogs for the v3 program editor."""

from __future__ import annotations

import os
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from editor.modules.editor.task_globals import get_available_sensors, get_available_valves
from modules.polynomial_pressure import (
    CONTROL_SENSOR_OPEN_LOOP,
    MAX_POLYNOMIAL_ORDER,
    build_pressure_profile,
    describe_pressure_function,
    is_open_loop_sensor,
    normalize_polynomial_pressure_params,
)
from modules.program_contract import (
    CONDITION_STABLE,
    PARAM_ACTION,
    PARAM_AMPLITUDE_MBAR,
    PARAM_CLAMP_MAX,
    PARAM_CLAMP_MIN,
    PARAM_COEFFICIENTS,
    PARAM_CONDITION,
    PARAM_CONTINUOUS,
    PARAM_DELTA_MBAR,
    PARAM_DURATION,
    PARAM_END_PRESSURE,
    PARAM_END_STEP,
    PARAM_FEEDBACK_GAIN,
    PARAM_FILENAME,
    PARAM_FILENAME_PREFIX,
    PARAM_FLOW_SENSOR,
    PARAM_FLUIDIC_VALVE,
    PARAM_FOLDER,
    PARAM_INPUT_PRESSURE,
    PARAM_KD,
    PARAM_KI,
    PARAM_KP,
    PARAM_MAX_CORRECTION,
    PARAM_MAX_PRESSURE,
    PARAM_MIN_PRESSURE,
    PARAM_MODE,
    PARAM_OFFSET_MBAR,
    PARAM_ORDER,
    PARAM_PATH,
    PARAM_PERIOD_S,
    PARAM_PHASE_DEG,
    PARAM_PNEUMATIC_VALVE,
    PARAM_PORT,
    PARAM_PRESSURE,
    PARAM_REPETITIONS,
    PARAM_SAMPLE_INTERVAL,
    PARAM_SAMPLING_INTERVAL_MS,
    PARAM_SENSOR,
    PARAM_SENSORS,
    PARAM_SLEW_LIMIT,
    PARAM_STABLE_TIME,
    PARAM_START_PRESSURE,
    PARAM_START_STEP,
    PARAM_STATUS,
    PARAM_TARGET_FLOW,
    PARAM_TARGET_VALUE,
    PARAM_TARGET_VOLUME,
    PARAM_TIME_SEC,
    PARAM_TOLERANCE,
    PARAM_TOLERANCE_PERCENT,
    PARAM_VALVE_NAME,
    PARAM_WAIT,
    ROTARY_ACTION_GOTO,
    ROTARY_ACTION_HOME,
    ROTARY_ACTION_NEXT,
    ROTARY_ACTION_PREV,
    STATUS_CLOSE,
    STATUS_OPEN,
    STEP_ADD_PRESSURE,
    STEP_CALIBRATE_WITH_FLUIGENT_SENSOR,
    STEP_DOSE_VOLUME,
    STEP_EXPORT_CSV,
    STEP_FLOW_CONTROLLER,
    STEP_LOAD_SEQUENCE,
    STEP_LOOP,
    STEP_POLYNOMIAL_PRESSURE,
    STEP_PRESSURE_RAMP,
    STEP_ROTARY_VALVE,
    STEP_SET_PRESSURE,
    STEP_SET_PRESSURE_ZERO,
    STEP_START_MEASUREMENT,
    STEP_STOP_MEASUREMENT,
    STEP_VALVE,
    STEP_WAIT,
    STEP_WAIT_FOR_SENSOR_EVENT,
    STEP_ZERO_FLUIGENT,
    sampling_interval_ms_from_params,
)


_NO_DIALOG_STEPS = {STEP_SET_PRESSURE_ZERO, STEP_STOP_MEASUREMENT}


def _as_float(params: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _as_int(params: dict, key: str, default: int = 0) -> int:
    try:
        return int(params.get(key, default))
    except (TypeError, ValueError):
        return int(default)


def _choice_index(values: list[str], current: object) -> int:
    current_text = str(current or "")
    try:
        return values.index(current_text)
    except ValueError:
        return 0


def _sensor_choices() -> list[str]:
    return [str(value) for value in get_available_sensors()]


def _flow_choices() -> list[str]:
    choices = [value for value in _sensor_choices() if "Flow" in value]
    return choices or ["Flow 1", "Flow 2", "Flow 3", "Flow 4"]


def _fluigent_choices() -> list[str]:
    return [value for value in _sensor_choices() if value.startswith("SN")]


def _valve_choices() -> list[str]:
    return [str(value) for value in get_available_valves()]


def _pneumatic_choices() -> list[str]:
    valves = _valve_choices()
    return [value for value in valves if "Pneumatic" in value] or valves


def _fluidic_choices() -> list[str]:
    valves = _valve_choices()
    return [value for value in valves if "Fluidic" in value] or valves


class _PathField(QWidget):
    """Line edit with a browse button used by file and folder parameters."""

    def __init__(self, mode: str, title: str, value: str = "", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.title = title
        self.edit = QLineEdit(str(value or ""))
        self.button = QPushButton("Browse...")
        self.button.clicked.connect(self._browse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    def value(self) -> str:
        """Return the selected path."""
        return self.edit.text().strip()

    def _browse(self) -> None:
        """Open the matching file dialog."""
        start = self.edit.text().strip() or ""
        if self.mode == "folder":
            path = QFileDialog.getExistingDirectory(self, self.title, start)
        else:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                self.title,
                start,
                "JSON files (*.json);;All files (*)",
            )
        if path:
            self.edit.setText(path)


class ParameterDialog(QDialog):
    """Small reusable form dialog for editor step parameters."""

    def __init__(self, title: str, fields: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._fields = fields
        self._widgets = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        root.addLayout(form)

        for field in fields:
            widget = self._make_widget(field)
            self._widgets[field["key"]] = widget
            form.addRow(QLabel(field["label"]), widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _make_widget(self, field: dict):
        field_type = field.get("type", "text")
        value = field.get("value")

        if field_type == "double":
            widget = QDoubleSpinBox()
            widget.setDecimals(int(field.get("decimals", 3)))
            widget.setRange(float(field.get("min", -1_000_000.0)), float(field.get("max", 1_000_000.0)))
            widget.setSingleStep(float(field.get("step", 1.0)))
            widget.setValue(float(value if value is not None else field.get("default", 0.0)))
            return widget

        if field_type == "int":
            widget = QSpinBox()
            widget.setRange(int(field.get("min", -1_000_000)), int(field.get("max", 1_000_000)))
            widget.setSingleStep(int(field.get("step", 1)))
            widget.setValue(int(value if value is not None else field.get("default", 0)))
            return widget

        if field_type == "combo":
            widget = QComboBox()
            choices = [str(choice) for choice in field.get("choices", [])]
            widget.addItems(choices)
            if choices:
                widget.setCurrentIndex(_choice_index(choices, value if value is not None else field.get("default", "")))
            return widget

        if field_type == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(value if value is not None else field.get("default", False)))
            return widget

        if field_type in {"file", "folder"}:
            return _PathField(field_type, field.get("title", field["label"]), str(value or ""))

        widget = QLineEdit(str(value if value is not None else field.get("default", "")))
        return widget

    def values(self) -> dict:
        """Return field values converted to the configured Python types."""
        values = {}
        for field in self._fields:
            key = field["key"]
            widget = self._widgets[key]
            field_type = field.get("type", "text")
            if field_type == "double":
                values[key] = float(widget.value())
            elif field_type == "int":
                values[key] = int(widget.value())
            elif field_type == "combo":
                values[key] = widget.currentText()
            elif field_type == "bool":
                values[key] = bool(widget.isChecked())
            elif field_type in {"file", "folder"}:
                values[key] = widget.value()
            else:
                values[key] = widget.text()
        return values


def _run_dialog(parent, title: str, fields: list[dict]) -> dict | None:
    dialog = ParameterDialog(title, fields, parent)
    if dialog.exec() != QDialog.Accepted:
        return None
    return dialog.values()


class PolynomialPressureDialog(QDialog):
    """Configure PolynomialPressure parameters with a live Qt6 Matplotlib preview."""

    def __init__(self, parent=None, params=None):
        super().__init__(parent)
        self.setWindowTitle("PolynomialPressure")
        self.resize(1060, 700)

        cfg = normalize_polynomial_pressure_params(params or {})
        coefficients = list(cfg["coefficients"])
        while len(coefficients) <= MAX_POLYNOMIAL_ORDER:
            coefficients.append(0.0)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Linear: P(t) = m*t + n", "linear")
        self.mode_combo.addItem("Quadratic: P(t) = a*t^2 + m*t + n", "quadratic")
        self.mode_combo.addItem("Cubic: P(t) = b*t^3 + a*t^2 + m*t + n", "cubic")
        self.mode_combo.addItem("Polynomial: c0 + c1*t + ...", "polynomial")
        self.mode_combo.addItem("Sine: offset + amplitude*sin(...)", "sine")
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
            spin = self._make_spin(coefficients[power], -100000.0, 100000.0, 6, 0.1, "")
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

        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(form_widget)
        form_scroll.setMinimumWidth(390)
        body.addWidget(form_scroll, 0)

        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(8)

        self.figure = None
        self.canvas = None
        self.ax = None
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            self.figure = Figure(figsize=(6.6, 4.2))
            self.canvas = FigureCanvasQTAgg(self.figure)
            self.ax = self.figure.add_subplot(111)
            preview_layout.addWidget(self.canvas, 1)
        except Exception as exc:
            preview_layout.addWidget(QLabel(f"Matplotlib preview unavailable:\n{exc}"), 1)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        preview_layout.addWidget(self.summary_label)
        body.addWidget(preview, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.mode_combo.currentIndexChanged.connect(self._on_input_changed)
        self.order_spin.valueChanged.connect(self._on_input_changed)
        self.duration_spin.valueChanged.connect(self._on_input_changed)
        for spin in self.coeff_spins:
            spin.valueChanged.connect(self._on_input_changed)
        for spin in (
            self.offset_spin,
            self.amplitude_spin,
            self.period_spin,
            self.phase_spin,
            self.clamp_min_spin,
            self.clamp_max_spin,
            self.slew_spin,
            self.sample_interval_spin,
            self.feedback_gain_spin,
            self.max_correction_spin,
        ):
            spin.valueChanged.connect(self._on_input_changed)
        self.sensor_combo.currentIndexChanged.connect(self._on_input_changed)

        self._on_input_changed()

    @staticmethod
    def _make_spin(value, minimum, maximum, decimals, step, suffix):
        spin = QDoubleSpinBox()
        spin.setRange(float(minimum), float(maximum))
        spin.setDecimals(int(decimals))
        spin.setSingleStep(float(step))
        spin.setValue(float(value))
        spin.setSuffix(str(suffix or ""))
        spin.setKeyboardTracking(True)
        return spin

    @staticmethod
    def _set_combo_value(combo, value):
        value = str(value or "")
        for index in range(combo.count()):
            if str(combo.itemData(index)) == value:
                combo.setCurrentIndex(index)
                return
        if value:
            combo.addItem(value, value)
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
        choices.extend(sensor for sensor in _sensor_choices() if str(sensor).startswith("SN"))
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
        """Return normalized PolynomialPressure parameters from the dialog."""
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
            coefficients = [self.coeff_spins[index].value() for index in range(order + 1)]
            params[PARAM_COEFFICIENTS] = coefficients
            params["n_mbar"] = coefficients[0]
            if order >= 1:
                params["m_mbar_per_s"] = coefficients[1]
            if order >= 2:
                params["a_mbar_per_s2"] = coefficients[2]
            if order >= 3:
                params["b_mbar_per_s3"] = coefficients[3]
        return normalize_polynomial_pressure_params(params)

    def update_preview(self):
        """Redraw the pressure-profile preview and summary."""
        params = self.to_params()
        preview_interval = max(0.02, params[PARAM_DURATION] / 240.0)
        points = build_pressure_profile(params, sample_interval=preview_interval)
        times = [point["time"] for point in points]
        raw = [point["raw"] for point in points]
        clamped = [point["clamped"] for point in points]
        limited = [point["limited"] for point in points]

        if self.ax is not None and self.canvas is not None:
            self.ax.clear()
            self.ax.plot(times, raw, color="#6b7280", linestyle="--", label="Raw")
            self.ax.plot(times, clamped, color="#d97706", linestyle=":", label="Clamped")
            self.ax.plot(times, limited, color="#0f6fa6", linewidth=2.0, label="Applied target")
            self.ax.set_xlabel("Time [s]")
            self.ax.set_ylabel("Pressure [mbar]")
            self.ax.set_xlim(0.0, max(1.0, params[PARAM_DURATION]))
            y_values = raw + clamped + limited + [params[PARAM_CLAMP_MIN], params[PARAM_CLAMP_MAX]]
            y_min = min(y_values)
            y_max = max(y_values)
            pad = max(5.0, 0.08 * max(1.0, y_max - y_min))
            self.ax.set_ylim(y_min - pad, y_max + pad)
            self.ax.grid(True, color="#dbe5ec", linestyle=":", linewidth=0.7)
            self.ax.legend(loc="best", frameon=False)
            self.figure.tight_layout()
            self.canvas.draw_idle()

        max_rate = 0.0
        for index in range(1, len(points)):
            dt = points[index]["time"] - points[index - 1]["time"]
            if dt > 0:
                max_rate = max(max_rate, abs(limited[index] - limited[index - 1]) / dt)

        sensor_text = "open-loop actuator setpoint"
        if not is_open_loop_sensor(params["sensor"]):
            sensor_text = (
                f"closed-loop on {params['sensor']} "
                f"(Kp={params['feedback_gain']:g}, max correction={params['max_correction']:g} mbar)"
            )
        self.summary_label.setText(
            f"{describe_pressure_function(params)} | Applied target: min {min(limited):.2f} mbar, "
            f"max {max(limited):.2f} mbar, end {limited[-1]:.2f} mbar, "
            f"max dP/dt {max_rate:.2f} mbar/s | {sensor_text}"
        )

    def accept(self):
        """Validate safety-relevant values before accepting."""
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


def _edit_polynomial_pressure(parent, params: dict) -> dict | None:
    dialog = PolynomialPressureDialog(parent, params)
    if dialog.exec() != QDialog.Accepted:
        return None
    return dialog.to_params()


def edit_step_params(parent, step_type: str, params: dict, step_count: int = 0) -> dict | None:
    """Open a task-specific editor and return updated params, or None when canceled."""
    params = deepcopy(params or {})
    if step_type in _NO_DIALOG_STEPS:
        return {}

    if step_type == STEP_SET_PRESSURE:
        return _run_dialog(parent, step_type, [
            {"key": PARAM_PRESSURE, "label": "Pressure [mbar]", "type": "double", "value": _as_float(params, PARAM_PRESSURE, 100.0)}
        ])

    if step_type == STEP_ADD_PRESSURE:
        return _run_dialog(parent, step_type, [
            {"key": PARAM_DELTA_MBAR, "label": "Delta pressure [mbar]", "type": "double", "value": _as_float(params, PARAM_DELTA_MBAR, 10.0)}
        ])

    if step_type == STEP_VALVE:
        valves = _valve_choices()
        if not valves:
            QMessageBox.warning(parent, "Valve", "No valves are available.")
            return None
        return _run_dialog(parent, step_type, [
            {"key": PARAM_VALVE_NAME, "label": "Valve", "type": "combo", "choices": valves, "value": params.get(PARAM_VALVE_NAME)},
            {"key": PARAM_STATUS, "label": "Status", "type": "combo", "choices": [STATUS_OPEN, STATUS_CLOSE], "value": params.get(PARAM_STATUS, STATUS_OPEN)},
        ])

    if step_type == STEP_WAIT:
        return _run_dialog(parent, step_type, [
            {"key": PARAM_TIME_SEC, "label": "Time [s]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_TIME_SEC, 5.0)}
        ])

    if step_type == STEP_WAIT_FOR_SENSOR_EVENT:
        sensors = _sensor_choices()
        if not sensors:
            QMessageBox.warning(parent, "Wait for Sensor Event", "No sensors are available.")
            return None
        values = _run_dialog(parent, step_type, [
            {"key": PARAM_SENSOR, "label": "Sensor", "type": "combo", "choices": sensors, "value": params.get(PARAM_SENSOR)},
            {"key": PARAM_CONDITION, "label": "Condition", "type": "combo", "choices": [">", "<", "=", CONDITION_STABLE], "value": params.get(PARAM_CONDITION, ">")},
            {"key": PARAM_TARGET_VALUE, "label": "Target value", "type": "double", "value": _as_float(params, PARAM_TARGET_VALUE, 0.0)},
            {"key": PARAM_TOLERANCE, "label": "Tolerance (+/-)", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_TOLERANCE, 1.0)},
            {"key": PARAM_STABLE_TIME, "label": "Stable time [s]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_STABLE_TIME, 5.0)},
        ])
        return values

    if step_type == STEP_START_MEASUREMENT:
        interval_ms = sampling_interval_ms_from_params(params, default=250)
        return _run_dialog(parent, step_type, [
            {"key": PARAM_SAMPLING_INTERVAL_MS, "label": "Interval [ms]", "type": "int", "min": 1, "max": 60_000, "value": interval_ms}
        ])

    if step_type == STEP_EXPORT_CSV:
        return _run_dialog(parent, step_type, [
            {"key": PARAM_FILENAME_PREFIX, "label": "Filename prefix", "type": "text", "value": params.get(PARAM_FILENAME_PREFIX, "Measurement")},
            {"key": PARAM_FOLDER, "label": "Export folder", "type": "folder", "title": "Select Export Folder", "value": params.get(PARAM_FOLDER, "")},
        ])

    if step_type == STEP_ZERO_FLUIGENT:
        choices = ["All"] + _fluigent_choices()
        current_sensors = params.get(PARAM_SENSORS) or []
        current_sensor = current_sensors[0] if isinstance(current_sensors, list) and current_sensors else "All"
        values = _run_dialog(parent, step_type, [
            {"key": PARAM_SENSORS, "label": "Sensor", "type": "combo", "choices": choices, "value": current_sensor}
        ])
        if values is None:
            return None
        selected = values.get(PARAM_SENSORS, "All")
        return {PARAM_SENSORS: [] if selected == "All" else [selected]}

    if step_type == STEP_LOOP:
        values = _run_dialog(parent, step_type, [
            {"key": PARAM_START_STEP, "label": "Start step", "type": "int", "min": 1, "max": max(1, step_count), "value": _as_int(params, PARAM_START_STEP, 1)},
            {"key": PARAM_END_STEP, "label": "End step", "type": "int", "min": 1, "max": max(1, step_count), "value": _as_int(params, PARAM_END_STEP, max(1, step_count))},
            {"key": PARAM_REPETITIONS, "label": "Repetitions", "type": "int", "min": 1, "max": 1_000_000, "value": _as_int(params, PARAM_REPETITIONS, 3)},
        ])
        if values and values[PARAM_END_STEP] < values[PARAM_START_STEP]:
            QMessageBox.warning(parent, "Loop", "End step must be greater than or equal to start step.")
            return None
        return values

    if step_type == STEP_DOSE_VOLUME:
        return _run_dialog(parent, step_type, [
            {"key": PARAM_FLOW_SENSOR, "label": "Flow sensor", "type": "combo", "choices": _flow_choices(), "value": params.get(PARAM_FLOW_SENSOR)},
            {"key": PARAM_PNEUMATIC_VALVE, "label": "Pneumatic valve", "type": "combo", "choices": _pneumatic_choices(), "value": params.get(PARAM_PNEUMATIC_VALVE)},
            {"key": PARAM_FLUIDIC_VALVE, "label": "Fluidic valve", "type": "combo", "choices": _fluidic_choices(), "value": params.get(PARAM_FLUIDIC_VALVE)},
            {"key": PARAM_TARGET_VOLUME, "label": "Target volume [uL]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_TARGET_VOLUME, 100.0)},
            {"key": PARAM_INPUT_PRESSURE, "label": "Input pressure [mbar]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_INPUT_PRESSURE, 200.0)},
        ])

    if step_type == STEP_ROTARY_VALVE:
        action = params.get(PARAM_ACTION, ROTARY_ACTION_GOTO)
        return _run_dialog(parent, step_type, [
            {"key": PARAM_ACTION, "label": "Action", "type": "combo", "choices": [ROTARY_ACTION_GOTO, ROTARY_ACTION_HOME, ROTARY_ACTION_PREV, ROTARY_ACTION_NEXT], "value": action},
            {"key": PARAM_PORT, "label": "Port", "type": "int", "min": 1, "max": 24, "value": _as_int(params, PARAM_PORT, 1)},
            {"key": PARAM_WAIT, "label": "Wait for completion", "type": "bool", "value": bool(params.get(PARAM_WAIT, True))},
        ])

    if step_type == STEP_PRESSURE_RAMP:
        return _run_dialog(parent, step_type, [
            {"key": PARAM_START_PRESSURE, "label": "Start pressure [mbar]", "type": "double", "value": _as_float(params, PARAM_START_PRESSURE, 0.0)},
            {"key": PARAM_END_PRESSURE, "label": "End pressure [mbar]", "type": "double", "value": _as_float(params, PARAM_END_PRESSURE, 100.0)},
            {"key": PARAM_DURATION, "label": "Duration [s]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_DURATION, 10.0)},
        ])

    if step_type == STEP_POLYNOMIAL_PRESSURE:
        return _edit_polynomial_pressure(parent, params)

    if step_type == STEP_FLOW_CONTROLLER:
        return _run_dialog(parent, step_type, [
            {"key": PARAM_TARGET_FLOW, "label": "Target flow [uL/min]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_TARGET_FLOW, 50.0)},
            {"key": PARAM_SENSOR, "label": "Flow sensor", "type": "combo", "choices": _flow_choices(), "value": params.get(PARAM_SENSOR)},
            {"key": PARAM_MAX_PRESSURE, "label": "Max pressure [mbar]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_MAX_PRESSURE, 350.0)},
            {"key": PARAM_MIN_PRESSURE, "label": "Min pressure [mbar]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_MIN_PRESSURE, 0.0)},
            {"key": PARAM_TOLERANCE_PERCENT, "label": "Tolerance [%]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_TOLERANCE_PERCENT, 5.0)},
            {"key": PARAM_STABLE_TIME, "label": "Stable time [s]", "type": "double", "min": 0.0, "value": _as_float(params, PARAM_STABLE_TIME, 5.0)},
            {"key": PARAM_CONTINUOUS, "label": "Continuous mode", "type": "bool", "value": bool(params.get(PARAM_CONTINUOUS, False))},
            {"key": PARAM_KP, "label": "Kp", "type": "double", "decimals": 4, "step": 0.01, "value": _as_float(params, PARAM_KP, 0.1)},
            {"key": PARAM_KI, "label": "Ki", "type": "double", "decimals": 4, "step": 0.01, "value": _as_float(params, PARAM_KI, 0.1)},
            {"key": PARAM_KD, "label": "Kd", "type": "double", "decimals": 4, "step": 0.01, "value": _as_float(params, PARAM_KD, 0.05)},
        ])

    if step_type == STEP_LOAD_SEQUENCE:
        values = _run_dialog(parent, step_type, [
            {"key": PARAM_PATH, "label": "Sequence file", "type": "file", "title": "Select Sequence File", "value": params.get(PARAM_PATH, "")}
        ])
        if values is None:
            return None
        path = values.get(PARAM_PATH, "")
        return {PARAM_FILENAME: os.path.basename(path), PARAM_PATH: path}

    if step_type == STEP_CALIBRATE_WITH_FLUIGENT_SENSOR:
        sensors = _fluigent_choices()
        if not sensors:
            QMessageBox.warning(parent, "Calibration", "No Fluigent sensors are available.")
            return None
        return _run_dialog(parent, step_type, [
            {"key": PARAM_SENSOR, "label": "Fluigent sensor", "type": "combo", "choices": sensors, "value": params.get(PARAM_SENSOR)}
        ])

    return _run_dialog(parent, step_type, [])


def format_step_summary(step: dict) -> str:
    """Return the human-readable program-step summary used by the v3 editor."""
    step_type = step.get("type", "")
    params = step.get("params", {}) or {}

    if step_type == STEP_SET_PRESSURE:
        return f"Set Pressure ({params.get(PARAM_PRESSURE, 0.0)} mbar)"
    if step_type == STEP_SET_PRESSURE_ZERO:
        return "Set Pressure to 0"
    if step_type == STEP_ADD_PRESSURE:
        return f"Add Pressure ({params.get(PARAM_DELTA_MBAR, 0.0)} mbar)"
    if step_type == STEP_VALVE:
        return f"Valve {params.get(PARAM_VALVE_NAME, 'Unknown')} ({params.get(PARAM_STATUS, STATUS_OPEN)})"
    if step_type == STEP_WAIT:
        return f"Wait ({params.get(PARAM_TIME_SEC, 1.0)} s)"
    if step_type == STEP_WAIT_FOR_SENSOR_EVENT:
        return (
            f"Sensor {params.get(PARAM_SENSOR, 'Unknown')} {params.get(PARAM_CONDITION, '>')} "
            f"{params.get(PARAM_TARGET_VALUE, 0.0)} (+/-{params.get(PARAM_TOLERANCE, 0.0)}, "
            f"{params.get(PARAM_STABLE_TIME, 0.0)}s)"
        )
    if step_type == STEP_START_MEASUREMENT:
        return f"Start Measurement (Interval: {sampling_interval_ms_from_params(params, default=250)} ms)"
    if step_type == STEP_STOP_MEASUREMENT:
        return "Stop Measurement"
    if step_type == STEP_EXPORT_CSV:
        return f"Export CSV (Prefix: {params.get(PARAM_FILENAME_PREFIX, 'Measurement')})"
    if step_type == STEP_ZERO_FLUIGENT:
        sensors = params.get(PARAM_SENSORS, [])
        return "Zero Fluigent Sensors (All)" if not sensors else f"Zero Fluigent Sensors ({', '.join(sensors)})"
    if step_type == STEP_LOOP:
        return f"Loop (Steps {params.get(PARAM_START_STEP, 1)}-{params.get(PARAM_END_STEP, 1)}, {params.get(PARAM_REPETITIONS, 1)}x)"
    if step_type == STEP_DOSE_VOLUME:
        return (
            f"Dose {params.get(PARAM_TARGET_VOLUME, 100.0)} uL @ {params.get(PARAM_INPUT_PRESSURE, '?')} mbar "
            f"({params.get(PARAM_PNEUMATIC_VALVE, '?')} -> {params.get(PARAM_FLUIDIC_VALVE, '?')})"
        )
    if step_type == STEP_ROTARY_VALVE:
        action = params.get(PARAM_ACTION, ROTARY_ACTION_GOTO)
        if action == ROTARY_ACTION_GOTO:
            return f"Rotary Valve (Goto {params.get(PARAM_PORT, 1)}, wait={params.get(PARAM_WAIT, True)})"
        return f"Rotary Valve ({action})"
    if step_type == STEP_PRESSURE_RAMP:
        return f"Pressure Ramp ({params.get(PARAM_START_PRESSURE, 0.0)} -> {params.get(PARAM_END_PRESSURE, 100.0)} mbar)"
    if step_type == STEP_POLYNOMIAL_PRESSURE:
        cfg = normalize_polynomial_pressure_params(params)
        sensor_text = "" if is_open_loop_sensor(cfg["sensor"]) else f", sensor={cfg['sensor']}"
        return (
            f"PolynomialPressure ({describe_pressure_function(cfg)}, {cfg['duration']:g}s, "
            f"clamp {cfg['clamp_min']:g}..{cfg['clamp_max']:g} mbar, "
            f"slew {cfg['slew_limit']:g} mbar/s{sensor_text})"
        )
    if step_type == STEP_FLOW_CONTROLLER:
        mode = "Continuous" if params.get(PARAM_CONTINUOUS, False) else "Stable"
        return (
            f"Flow Controller (Target: {params.get(PARAM_TARGET_FLOW, 50.0)} uL/min, "
            f"Max: {params.get(PARAM_MAX_PRESSURE, 350.0)} mbar, "
            f"Min: {params.get(PARAM_MIN_PRESSURE, 0.0)} mbar, {mode})"
        )
    if step_type == STEP_LOAD_SEQUENCE:
        return f"Load Sequence ({params.get(PARAM_FILENAME, 'Unknown')})"
    if step_type == STEP_CALIBRATE_WITH_FLUIGENT_SENSOR:
        return f"Calibrate With {params.get(PARAM_SENSOR, 'Unknown')}"
    return str(step_type or "<missing>")
