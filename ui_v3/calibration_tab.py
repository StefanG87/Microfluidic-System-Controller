"""PySide6 calibration page for EtOH flow-by-mass calibration."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.balance import SerialBalance
from modules.medium_calibration_core.analysis import CalibrationAnalyzer
from modules.medium_calibration_core.lookup import DensityLookup, PressureOffsetStore
from modules.medium_calibration_core.measurement import CalibrationRunner, MeasurementPlan
from modules.medium_calibration_core.models import CalibrationSession


@dataclass
class CalibrationHardwareContext:
    """Hardware references needed by the calibration page."""

    pressure_source: Any | None
    valves: list[Any]
    valve_labels: list[str]
    valve_groups: list[str]
    flow_sensors: list[Any]
    pressure_sensors: list[Any]
    pressure_offset_mbar: float = 0.0
    balance: Any | None = None
    balance_port: str = ""
    log: Any | None = None


class _InternalPressureSensor:
    """Adapter that exposes the controller's internal pressure monitor as a sensor."""

    device_sn = "Internal"

    def __init__(self, controller: Any):
        self.controller = controller

    def read_pressure(self) -> float | None:
        """Read corrected pressure from the controller's internal monitor path."""
        measured = self.controller.read_internal_pressure_mbar()
        if measured is None:
            return None
        return float(measured) - float(getattr(self.controller, "offset", 0.0) or 0.0)


def hardware_context_from_controller(controller: Any) -> CalibrationHardwareContext:
    """Build a calibration hardware context from the v3 runtime controller."""
    valve_meta = list(getattr(controller, "_valve_meta", []) or [])
    valve_labels = []
    valve_groups = []
    for index, meta in enumerate(valve_meta):
        valve_labels.append(
            str(meta.get("button_label") or meta.get("editor_name") or f"Valve {index + 1}")
        )
        valve_groups.append(str(meta.get("group", "")).lower())
    valves = list(getattr(controller, "valves", []) or [])
    if len(valve_labels) < len(valves):
        valve_labels.extend(f"Valve {index + 1}" for index in range(len(valve_labels), len(valves)))
    if len(valve_groups) < len(valves):
        valve_groups.extend("" for _index in range(len(valve_groups), len(valves)))

    pressure_sensors = list(getattr(controller, "fluigent_sensors", []) or [])
    if not pressure_sensors and getattr(controller, "pressure_source", None) is not None:
        pressure_sensors.append(_InternalPressureSensor(controller))

    return CalibrationHardwareContext(
        pressure_source=getattr(controller, "pressure_source", None),
        valves=valves,
        valve_labels=valve_labels,
        valve_groups=valve_groups,
        flow_sensors=list(getattr(controller, "flow_sensors", []) or []),
        pressure_sensors=pressure_sensors,
        pressure_offset_mbar=float(getattr(controller, "offset", 0.0) or 0.0),
        balance=getattr(controller, "balance_reader", None),
        balance_port=str(getattr(controller, "balance_port", "") or ""),
        log=getattr(controller, "append_log", None),
    )


class _CalibrationWorker(QObject):
    """Run the blocking calibration sequence outside the GUI thread."""

    finished = Signal(object)
    failed = Signal(str)
    log_line = Signal(str)
    next_tube_requested = Signal(int, float)

    def __init__(
        self,
        hardware: CalibrationHardwareContext,
        session: CalibrationSession,
        plan: MeasurementPlan,
        flow_index: int,
        pressure_index: int,
        pneumatic_index: int,
        fluidic_index: int,
        balance_port: str = "",
    ):
        super().__init__()
        self.hardware = hardware
        self.session = session
        self.plan = plan
        self.flow_index = flow_index
        self.pressure_index = pressure_index
        self.pneumatic_index = pneumatic_index
        self.fluidic_index = fluidic_index
        self.balance_port = str(balance_port or "").strip()
        self._continue_event = Event()
        self._continue_ok = True
        self._runner: CalibrationRunner | None = None

    def run(self) -> None:
        """Create the runner and execute the selected calibration plan."""
        balance = None
        owns_balance = False
        try:
            balance = self.hardware.balance
            connected_port = str(getattr(balance, "port", "") or "").strip()
            if self.balance_port and (balance is None or connected_port != self.balance_port):
                balance = SerialBalance(self.balance_port)
                owns_balance = True
                self.log_line.emit(f"Balance connected on {self.balance_port}")
            elif balance is not None:
                self.log_line.emit(f"Using connected balance on {connected_port or 'selected port'}")

            runner = CalibrationRunner(
                pressure_source=self.hardware.pressure_source,
                pneumatic_valve=self.hardware.valves[self.pneumatic_index],
                fluidic_valve=self.hardware.valves[self.fluidic_index],
                flow_sensor=self.hardware.flow_sensors[self.flow_index],
                pressure_sensor=self.hardware.pressure_sensors[self.pressure_index],
                session=self.session,
                balance=balance,
                wait_for_next_tube=self._wait_for_next_tube,
                log=self.log_line.emit,
            )
            self._runner = runner
            self.finished.emit(runner.run(self.plan))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if owns_balance and balance is not None:
                try:
                    balance.close()
                except Exception:
                    pass

    def stop(self) -> None:
        """Request a cooperative stop."""
        if self._runner is not None:
            self._runner.stop()
        self._continue_ok = False
        self._continue_event.set()

    def continue_after_tube_dialog(self, ok: bool) -> None:
        """Continue or abort after the operator changed the collection tube."""
        self._continue_ok = bool(ok)
        self._continue_event.set()

    def _wait_for_next_tube(self, next_repeat: int, next_pressure: float) -> bool:
        """Ask the GUI thread to wait for the operator between repeats."""
        self._continue_event.clear()
        self.next_tube_requested.emit(next_repeat, next_pressure)
        self._continue_event.wait()
        return self._continue_ok


class MediumCalibrationTab(QWidget):
    """Calibration page for flow-sensor correction by gravimetric mass data."""

    def __init__(
        self,
        hardware: CalibrationHardwareContext | None = None,
        hardware_provider=None,
        density_lookup: DensityLookup | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.hardware = hardware
        self.hardware_provider = hardware_provider
        self.density_lookup = density_lookup or DensityLookup.load()
        self.offset_store = PressureOffsetStore()
        self.session: CalibrationSession | None = None
        self.worker_thread: QThread | None = None
        self.worker: _CalibrationWorker | None = None
        self._build_ui()
        self._load_hardware_choices()
        self._update_density()

    def set_hardware_context(self, hardware: CalibrationHardwareContext | None) -> None:
        """Replace hardware references after connect, refresh, or profile changes."""
        self.hardware = hardware
        self._load_hardware_choices()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.setup_page = QWidget()
        self.live_page = QWidget()
        self.results_page = QWidget()
        self.tabs.addTab(self.setup_page, "Setup")
        self.tabs.addTab(self.live_page, "Live Measurement")
        self.tabs.addTab(self.results_page, "Results")

        self._build_setup_page()
        self._build_live_page()
        self._build_results_page()

    def _build_setup_page(self) -> None:
        root = QVBoxLayout(self.setup_page)
        form = QFormLayout()
        root.addLayout(form)

        self.context_label = QLabel("No hardware context")
        self.context_label.setWordWrap(True)
        form.addRow("Hardware", self.context_label)

        self.etoh_input = QDoubleSpinBox()
        self.etoh_input.setRange(0.0, 100.0)
        self.etoh_input.setDecimals(2)
        self.etoh_input.setSingleStep(0.5)
        self.etoh_input.valueChanged.connect(self._update_density)
        form.addRow("EtOH [%]", self.etoh_input)

        self.density_label = QLabel("-")
        form.addRow("Density [g/cm3]", self.density_label)

        self.duration_input = QDoubleSpinBox()
        self.duration_input.setRange(1.0, 3600.0)
        self.duration_input.setValue(10.0)
        self.duration_input.setDecimals(1)
        form.addRow("Measurement time [s]", self.duration_input)

        self.cut_input = QDoubleSpinBox()
        self.cut_input.setRange(0.0, 30.0)
        self.cut_input.setValue(0.7)
        self.cut_input.setDecimals(2)
        form.addRow("Warmup cut [s]", self.cut_input)

        self.pressures_input = QLineEdit("25,50,100,150,200")
        form.addRow("Pressure stages [mbar]", self.pressures_input)

        self.repeats_input = QSpinBox()
        self.repeats_input.setRange(1, 99)
        self.repeats_input.setValue(3)
        form.addRow("Repeats per pressure", self.repeats_input)

        self.flow_combo = QComboBox()
        form.addRow("Flow sensor", self.flow_combo)

        self.pressure_combo = QComboBox()
        form.addRow("Pressure sensor", self.pressure_combo)

        self.pneumatic_combo = QComboBox()
        form.addRow("Pneumatic valve", self.pneumatic_combo)

        self.fluidic_combo = QComboBox()
        form.addRow("Fluidic valve", self.fluidic_combo)

        self.balance_port_input = QLineEdit()
        self.balance_port_input.setPlaceholderText("optional, e.g. COM5")
        form.addRow("Balance COM port", self.balance_port_input)

        self.mode_label = QLabel(
            "Balance setup follows the Ohaus SOP: 9600 baud, 8N1, no flow control, "
            "unit g, and auto-print at about 1 s. Leave COM empty if the mass is entered "
            "or processed manually later."
        )
        self.mode_label.setWordWrap(True)
        root.addWidget(self.mode_label)

        buttons = QHBoxLayout()
        root.addLayout(buttons)
        self.refresh_button = QPushButton("Refresh hardware")
        self.refresh_button.clicked.connect(self.refresh_hardware_context)
        buttons.addWidget(self.refresh_button)

        self.start_button = QPushButton("Start calibration")
        self.start_button.clicked.connect(self.start_calibration)
        buttons.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_calibration)
        buttons.addWidget(self.stop_button)

        self.save_button = QPushButton("Save calibration JSON")
        self.save_button.clicked.connect(self.save_calibration)
        self.save_button.setEnabled(False)
        buttons.addWidget(self.save_button)

        root.addStretch()

    def _build_live_page(self) -> None:
        root = QVBoxLayout(self.live_page)

        values = QGroupBox("Current values")
        values_layout = QFormLayout(values)
        self.status_label = QLabel("Idle")
        self.live_pressure_label = QLabel("-")
        self.live_sensor_flow_label = QLabel("-")
        self.live_mass_label = QLabel("-")
        self.live_grav_flow_label = QLabel("-")
        values_layout.addRow("Status", self.status_label)
        values_layout.addRow("Pressure [mbar]", self.live_pressure_label)
        values_layout.addRow("Sensor flow [uL/min]", self.live_sensor_flow_label)
        values_layout.addRow("Mass [g]", self.live_mass_label)
        values_layout.addRow("Grav. flow [uL/min]", self.live_grav_flow_label)
        root.addWidget(values)

        self.live_hint = QLabel(
            "During each repeat the pneumatic valve stays open and the selected fluidic "
            "valve opens for the measurement window. The runner closes valves and sends "
            "0 mbar in its cleanup path."
        )
        self.live_hint.setWordWrap(True)
        root.addWidget(self.live_hint)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        root.addWidget(self.log, 1)

    def _build_results_page(self) -> None:
        root = QVBoxLayout(self.results_page)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Target",
                "Repeat",
                "Pressure mean",
                "Sensor mean",
                "Sensor std",
                "Mass start",
                "Mass end",
                "Delta mass",
                "Grav flow",
            ]
        )
        root.addWidget(self.table, 1)

        self.fit_label = QLabel("Fit: -")
        root.addWidget(self.fit_label)

    def _load_hardware_choices(self) -> None:
        """Refresh combo boxes from the current runtime hardware context."""
        self.flow_combo.clear()
        self.pressure_combo.clear()
        self.pneumatic_combo.clear()
        self.fluidic_combo.clear()

        if self.hardware is None or self.hardware.pressure_source is None:
            self.context_label.setText("No connected hardware context")
            for combo in (self.flow_combo, self.pressure_combo, self.pneumatic_combo, self.fluidic_combo):
                combo.addItem("No hardware context", None)
            self.start_button.setEnabled(False)
            return

        self.context_label.setText(
            f"{len(self.hardware.flow_sensors)} flow sensor(s), "
            f"{len(self.hardware.pressure_sensors)} pressure sensor(s), "
            f"{len(self.hardware.valves)} valve(s), "
            f"offset {self.hardware.pressure_offset_mbar:.2f} mbar"
        )
        if self.hardware.balance_port and not self.balance_port_input.text().strip():
            self.balance_port_input.setText(self.hardware.balance_port)

        for index, sensor in enumerate(self.hardware.flow_sensors):
            self.flow_combo.addItem(getattr(sensor, "name", f"Flow {index + 1}"), index)

        for index, sensor in enumerate(self.hardware.pressure_sensors):
            label = getattr(sensor, "device_sn", "")
            self.pressure_combo.addItem(f"SN{label}" if label and label != "Internal" else "Internal", index)

        for index, _valve in enumerate(self.hardware.valves):
            label = self.hardware.valve_labels[index] if index < len(self.hardware.valve_labels) else f"Valve {index + 1}"
            group = self.hardware.valve_groups[index] if index < len(self.hardware.valve_groups) else ""
            if group == "pneumatic" or (not group and index < 4):
                self.pneumatic_combo.addItem(label, index)
            elif group == "fluidic" or (not group and index >= 4):
                self.fluidic_combo.addItem(label, index)

        self.start_button.setEnabled(
            bool(self.hardware.flow_sensors)
            and bool(self.hardware.pressure_sensors)
            and self.pneumatic_combo.count() > 0
            and self.fluidic_combo.count() > 0
        )

    def refresh_hardware_context(self) -> None:
        """Reload hardware references from the provider passed by the v3 shell."""
        if self.hardware_provider is not None:
            self.hardware = self.hardware_provider()
        self._load_hardware_choices()

    def _update_density(self) -> None:
        """Show the interpolated EtOH density for the selected composition."""
        try:
            density = self.density_lookup.density(self.etoh_input.value())
            self.density_label.setText(f"{density:.5f}")
        except Exception as exc:
            self.density_label.setText(str(exc))

    def start_calibration(self) -> None:
        """Validate inputs and start a calibration worker."""
        if self.hardware is None:
            QMessageBox.warning(self, "Calibration", "No hardware context available.")
            return
        try:
            pressures = [float(p.strip().replace(",", ".")) for p in self.pressures_input.text().split(",") if p.strip()]
            density = self.density_lookup.density(self.etoh_input.value())
            if not pressures:
                raise ValueError("At least one pressure stage is required.")
        except Exception as exc:
            QMessageBox.warning(self, "Calibration", f"Invalid input: {exc}")
            return

        self.session = CalibrationSession(
            etoh_percent=float(self.etoh_input.value()),
            density_g_cm3=float(density),
            measurement_duration_s=float(self.duration_input.value()),
            warmup_cut_s=float(self.cut_input.value()),
            metadata={"source": "Microfluidic System Controller v3"},
        )
        offset = float(self.hardware.pressure_offset_mbar)
        if offset == 0.0:
            offset = self.offset_store.load(default=0.0)
        plan = MeasurementPlan(
            pressures_mbar=pressures,
            repetitions=int(self.repeats_input.value()),
            duration_s=float(self.duration_input.value()),
            warmup_cut_s=float(self.cut_input.value()),
            pressure_offset_mbar=offset,
        )

        self.worker = _CalibrationWorker(
            hardware=self.hardware,
            session=self.session,
            plan=plan,
            flow_index=int(self.flow_combo.currentData()),
            pressure_index=int(self.pressure_combo.currentData()),
            pneumatic_index=int(self.pneumatic_combo.currentData()),
            fluidic_index=int(self.fluidic_combo.currentData()),
            balance_port=self.balance_port_input.text().strip(),
        )
        self.worker_thread = QThread(self)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.log_line.connect(self._append_log)
        self.worker.next_tube_requested.connect(self._on_next_tube)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.failed.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._clear_worker_refs)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self.table.setRowCount(0)
        self.status_label.setText("Running")
        self.tabs.setCurrentWidget(self.live_page)
        self._append_log("Calibration started.")
        self.worker_thread.start()

    def stop_calibration(self) -> None:
        """Request calibration stop."""
        if self.worker is not None:
            self.worker.stop()
        self._append_log("Stop requested.")

    def save_calibration(self) -> None:
        """Save the completed calibration JSON into the shared calibration folder."""
        if self.session is None:
            return
        path = CalibrationAnalyzer(self.session).save()
        QMessageBox.information(self, "Calibration saved", str(path))
        self._append_log(f"Saved {path}")

    def _on_finished(self, session: CalibrationSession) -> None:
        """Populate result tables after a successful calibration."""
        self.session = session
        self._refresh_table()
        self._append_log("Calibration finished.")
        self.status_label.setText("Finished")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(bool(session.records))
        self.tabs.setCurrentWidget(self.results_page)

    def _on_failed(self, message: str) -> None:
        """Show one calibration failure without taking down the app."""
        self._append_log(f"ERROR: {message}")
        self.status_label.setText("Failed")
        QMessageBox.critical(self, "Calibration failed", message)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _clear_worker_refs(self) -> None:
        """Drop stale worker/thread references."""
        self.worker = None
        self.worker_thread = None

    def _on_next_tube(self, next_repeat: int, next_pressure: float) -> None:
        """Pause between collection tubes and let the operator continue or cancel."""
        box = QMessageBox(self)
        box.setWindowTitle("Next tube")
        box.setText(
            f"Move tubing to the next collection tube.\n\n"
            f"Next repeat: {next_repeat}\n"
            f"Target pressure: {next_pressure:.1f} mbar"
        )
        box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Ok)
        ok = box.exec() == QMessageBox.StandardButton.Ok
        if self.worker is not None:
            self.worker.continue_after_tube_dialog(ok)

    def _refresh_table(self) -> None:
        """Refresh the results table from the current session."""
        if self.session is None:
            return
        analyzer = CalibrationAnalyzer(self.session)
        rows = analyzer.repeat_rows()
        self.table.setRowCount(len(rows))
        for row, data in enumerate(rows):
            values = [
                data["target_pressure_mbar"],
                data["repeat_index"],
                data["pressure_mean_mbar"],
                data["sensor_mean_ul_min"],
                data["sensor_std_ul_min"],
                data["mass_start_g"],
                data["mass_end_g"],
                data["delta_mass_g"],
                data["grav_flow_ul_min"],
            ]
            for col, value in enumerate(values):
                text = "" if value is None else f"{value:.4g}" if isinstance(value, float) else str(value)
                self.table.setItem(row, col, QTableWidgetItem(text))
        fit = analyzer.fit()
        if fit is None:
            self.fit_label.setText("Fit: not enough gravimetric data")
        else:
            self.fit_label.setText(
                f"Fit: Q_grav = {fit.slope:.6g} * Q_sensor + {fit.intercept:.6g}, R2 = {fit.r2:.5f}"
            )

    def _append_log(self, message: str) -> None:
        """Append one line to the calibration and runtime logs."""
        self.log.append(str(message))
        if self.hardware is not None and self.hardware.log is not None:
            try:
                self.hardware.log(str(message))
            except Exception:
                pass
