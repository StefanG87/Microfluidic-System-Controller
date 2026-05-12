"""Controller facade used by the v3 GUI.

The v3 widgets call this class instead of talking to hardware modules directly.
It also implements the GUI-facing adapter methods expected by ProgramRunner.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from editor.modules.editor.task_globals import update_available_sensors, update_available_valves
from modules.csv_exporter import CSVExporter
from modules.flow_sensor import SensirionFlowSensor
from modules.fluigent_wrapper import detect_fluigent_sensors
from modules.measurement_sampler import MeasurementSampler
from modules.measurement_session import MeasurementSession
from modules.mf_common import (
    list_hw_profiles,
    load_hardware_profile,
    load_hw_profile_from_prefs,
    load_last_comport,
    load_last_modbus_ip,
    load_pressure_offset,
    save_hw_profile_to_prefs,
    save_last_modbus_ip,
    save_pressure_offset,
)
from modules.pressure_controller import PressureController
from modules.program_runner import ProgramRunner
from modules.runtime_devices import RuntimeDeviceRegistry
from modules.valve import Valve
from modules.device_catalog import valve_meta_from_profile_item
from ui_v3.controllers.program_worker import V3ProgramWorker
from ui_v3.controllers.timebase import V3Timebase


class V3RuntimeController(QObject):
    """Qt6-facing controller for runtime state, measurement, export, and programs."""

    log_message = Signal(str)
    status_changed = Signal(object)
    device_catalog_changed = Signal(object)
    sample_ready = Signal(object)
    sample_failed = Signal(str)
    measurement_state_changed = Signal(bool)
    program_state_changed = Signal(bool)
    program_finished = Signal()
    program_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.offset = load_pressure_offset()
        self.target_pressure = 0.0
        self.sampling_interval_ms = 250
        self.hardware_connected = False
        self.is_measuring = False
        self.modbus = None
        self.pressure_source = None
        self.flow_sensors = []
        self.fluigent_sensors = []
        self.valves = []
        self._valve_meta = []
        self.hw_profile = {"name": "not connected", "valve_groups": []}
        self.hw_profile_source = load_hw_profile_from_prefs(default="stand1")

        self.timebase = V3Timebase()
        self.timebase.set_sampling_interval_ms(self.sampling_interval_ms)
        self.measurement_session = MeasurementSession(flow_channel_count=0)
        self.runtime_devices = RuntimeDeviceRegistry()
        self.device_catalog = self.runtime_devices.catalog
        self.measurement_sampler = MeasurementSampler(
            self.runtime_devices,
            self.measurement_session,
            self.timebase,
        )
        self._last_status = {}

        self.timer = QTimer(self)
        self.timer.setInterval(self.sampling_interval_ms)
        self.timer.timeout.connect(self.sample_once)

        self.program_runner = ProgramRunner(self)
        self.program_thread = None
        self.program_worker = None
        self.rotary_adapter = None
        self.rotary_active_port = 0
        self._sample_failure_logged = False
        self._publish_device_catalog()
        self._emit_status()

    def append_log(self, text) -> None:
        """ProgramRunner-compatible logging endpoint."""
        self.log_message.emit(str(text))

    def connect_hardware(self, ip: str | None = None, profile_name: str | None = None) -> bool:
        """Connect hardware and publish the detected runtime catalog."""
        try:
            from pymodbus.client import ModbusTcpClient
        except Exception as exc:
            self.append_log(f"[v3] pymodbus is not available: {exc}")
            self._emit_status()
            return False

        candidates = self._modbus_candidates(ip)
        errors = []
        for candidate in candidates:
            client = ModbusTcpClient(candidate, port=502, timeout=1.2)
            try:
                if client.connect():
                    self.modbus = client
                    save_last_modbus_ip(candidate)
                    self._initialize_hardware(profile_name)
                    self.hardware_connected = True
                    self.timebase.reset_time()
                    self.measurement_session.reset()
                    self.timer.start(self.sampling_interval_ms)
                    self.append_log(f"[v3] Connected to Modbus at {candidate}")
                    self._emit_status()
                    return True
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")
            try:
                client.close()
            except Exception:
                pass
        self.append_log("[v3] Modbus connection failed: " + (", ".join(errors) or ", ".join(candidates)))
        self._emit_status()
        return False

    def disconnect_hardware(self) -> None:
        """Stop measurement and release the Modbus connection."""
        self.stop_measurement()
        if self.timer.isActive():
            self.timer.stop()
        try:
            self.close_all_valves()
            self.reset_pressure_hardware_zero_mbar()
        except Exception as exc:
            self.append_log(f"[v3] Reset during disconnect failed: {exc}")
        try:
            if self.modbus is not None:
                self.modbus.close()
        except Exception as exc:
            self.append_log(f"[v3] Modbus close failed: {exc}")
        self.hardware_connected = False
        self.modbus = None
        self.pressure_source = None
        self.flow_sensors = []
        self.fluigent_sensors = []
        self.valves = []
        self._valve_meta = []
        self.runtime_devices.set_pressure_source(None)
        self.runtime_devices.set_flow_sensors([])
        self.runtime_devices.set_fluigent_sensors([])
        self.runtime_devices.set_valves([], [])
        self.runtime_devices.rebuild_catalog()
        self.measurement_session.set_flow_channel_count(0)
        self.measurement_session.set_fluigent_channel_count(0)
        self._publish_device_catalog()
        self._emit_status()

    def shutdown_for_close(self) -> None:
        """Best-effort safe shutdown used when the v3 main window closes."""
        try:
            self.stop_program()
            thread = self.program_thread
            if thread is not None:
                try:
                    thread.wait(2000)
                except RuntimeError:
                    pass
        except Exception as exc:
            self.append_log(f"[v3] Program stop during shutdown failed: {exc}")

        try:
            self.disconnect_hardware()
        except Exception as exc:
            self.append_log(f"[v3] Hardware shutdown failed: {exc}")

    def refresh_device_catalog(self) -> str:
        """Refresh detectable devices without changing hardware outputs."""
        if not self.hardware_connected:
            message = "[v3] Connect hardware before refreshing devices."
            self.append_log(message)
            self._publish_device_catalog()
            self._emit_status()
            return message

        result = self.runtime_devices.refresh_detectable_devices(
            self.read_internal_pressure_mbar,
            detect_fluigent_sensors,
        )
        self.fluigent_sensors = self.runtime_devices.fluigent_sensors
        self.measurement_session.set_fluigent_channel_count(len(self.fluigent_sensors))
        self._publish_device_catalog()
        self.append_log(f"[v3] {result.summary}")
        self._emit_status()
        return result.summary

    def _modbus_candidates(self, explicit_ip: str | None) -> list[str]:
        """Return Modbus candidates in the same spirit as the classic GUI."""
        candidates = []
        if explicit_ip and explicit_ip.strip():
            candidates.append(explicit_ip.strip())
        last_ip = load_last_modbus_ip()
        if last_ip and last_ip not in candidates:
            candidates.append(last_ip)
        env_ips = os.environ.get("MF_MODBUS_IPS", "")
        for ip in env_ips.split(","):
            ip = ip.strip()
            if ip and ip not in candidates:
                candidates.append(ip)
        for ip in ["192.168.1.100", "192.168.0.100", "192.168.1.10", "192.168.1.50"]:
            if ip not in candidates:
                candidates.append(ip)
        return candidates

    def _initialize_hardware(self, profile_name: str | None) -> None:
        """Create runtime hardware adapters after Modbus has connected."""
        self.pressure_source = PressureController(self.modbus, register=1, type=2)
        self.runtime_devices.set_pressure_source(self.pressure_source)

        active_profile = profile_name or load_hw_profile_from_prefs(default="stand1")
        self.hw_profile_source = active_profile
        self.hw_profile = load_hardware_profile(active_profile)
        save_hw_profile_to_prefs(active_profile)
        self._build_valves_from_profile()

        self.flow_sensors = [
            SensirionFlowSensor(
                self.modbus,
                register=4 + index,
                name=f"Flow {index + 1}",
                v_min=0.0,
                v_max=10.0,
                flow_min=0.0,
                flow_max=1000.0,
            )
            for index in range(4)
        ]
        self.measurement_session.set_flow_channel_count(len(self.flow_sensors))
        self.runtime_devices.set_flow_sensors(self.flow_sensors)

        self.fluigent_sensors = detect_fluigent_sensors()
        self.measurement_session.set_fluigent_channel_count(len(self.fluigent_sensors))
        self.runtime_devices.set_fluigent_sensors(self.fluigent_sensors)

        self.runtime_devices.rebuild_catalog()
        self._publish_device_catalog()

    def _build_valves_from_profile(self) -> None:
        """Build valve objects and metadata from the active hardware profile."""
        self.valves = []
        self._valve_meta = []
        for group in self.hw_profile.get("valve_groups", []):
            for item in group.get("items", []):
                valve = Valve(self.modbus, int(item["coil"]))
                self.valves.append(valve)
                self._valve_meta.append(valve_meta_from_profile_item(group, item))
        self.runtime_devices.set_valves(self.valves, self._valve_meta)

    def available_hardware_profiles(self) -> list[str]:
        """Return hardware-profile names available from the lookup folder."""
        return list_hw_profiles() or ["stand1"]

    def set_hardware_profile(self, profile_name_or_path: str, persist: bool = True) -> bool:
        """Apply a hardware profile without changing pressure or sensor configuration."""
        profile_key = str(profile_name_or_path or "").strip()
        if not profile_key:
            self.append_log("[v3] Hardware profile is empty.")
            return False
        if self.program_thread_is_running():
            self.append_log("[v3] Stop the running program before changing the hardware profile.")
            return False
        if self.is_measuring:
            self.append_log("[v3] Stop the measurement before changing the hardware profile.")
            return False

        profile = load_hardware_profile(profile_key)
        if not profile.get("valve_groups"):
            self.append_log(f"[v3] Hardware profile has no valve groups: {profile_key}")
            return False

        if self.hardware_connected:
            try:
                self.close_all_valves()
            except Exception as exc:
                self.append_log(f"[v3] Could not close valves before profile switch: {exc}")
                return False

        self.hw_profile_source = profile_key
        self.hw_profile = profile

        if self.hardware_connected and self.modbus is not None:
            self._build_valves_from_profile()
        else:
            self.valves = []
            self._valve_meta = []
            self.runtime_devices.set_valves([], [])

        self.runtime_devices.rebuild_catalog()
        if persist:
            save_hw_profile_to_prefs(profile_key)
        self._publish_device_catalog()
        self.append_log(f"[v3] Hardware profile set to '{self.hw_profile.get('name', profile_key)}'.")
        self._emit_status()
        return True

    def _publish_device_catalog(self) -> None:
        """Publish devices for editor dialogs and notify v3 widgets."""
        update_available_valves(self.device_catalog.valve_names())
        update_available_sensors(self.device_catalog.sensor_names())
        self.device_catalog_changed.emit(self.device_catalog.to_embedded_editor_info())

    def _emit_status(self) -> None:
        """Emit a compact status snapshot for the status bar and settings page."""
        valve_states = []
        try:
            valve_states = list(self.runtime_devices.read_valve_states())
        except Exception as exc:
            self.append_log(f"[v3] Valve state snapshot failed: {exc}")
        self._last_status = {
            "connected": self.hardware_connected,
            "measuring": self.is_measuring,
            "program_running": self.program_thread_is_running(),
            "profile": self.hw_profile.get("name", "-"),
            "profile_source": self.hw_profile_source,
            "sampling_interval_ms": self.sampling_interval_ms,
            "target_pressure": self.target_pressure,
            "offset": self.offset,
            "valve_names": self.device_catalog.valve_names(),
            "valve_states": valve_states,
        }
        self.status_changed.emit(dict(self._last_status))

    def status_snapshot(self) -> dict:
        """Return the latest controller status for widgets connected after startup."""
        return dict(self._last_status)

    def set_sampling_interval_ms(self, interval_ms: int) -> None:
        """Apply a sampling interval in milliseconds."""
        self.sampling_interval_ms = max(1, int(interval_ms))
        self.timebase.set_sampling_interval_ms(self.sampling_interval_ms)
        self.timer.setInterval(self.sampling_interval_ms)
        self._emit_status()

    def start_measurement(self) -> None:
        """Reset the live plot buffers and mark a measurement run as active."""
        if not self.hardware_connected or self.pressure_source is None:
            self.append_log("[v3] Connect hardware before starting a measurement.")
            self._emit_status()
            return
        self.measurement_session.reset()
        self.timebase.reset_time()
        self.is_measuring = True
        if not self.timer.isActive():
            self.timer.start(self.sampling_interval_ms)
        self.measurement_state_changed.emit(True)
        self.append_log("[v3] Measurement started.")
        self._emit_status()

    def stop_measurement(self) -> None:
        """Mark the measurement as stopped while live monitoring continues."""
        if self.is_measuring:
            self.append_log("[v3] Measurement stopped.")
        self.is_measuring = False
        self.measurement_state_changed.emit(False)
        self._emit_status()

    def measurement_has_data(self) -> bool:
        """Return True when the current session contains at least one sample."""
        return bool(self.measurement_session.time_data)

    def suggest_csv_path(self, prefix: str = "measurement_v3") -> str:
        """Return the default CSV path used by manual v3 exports."""
        folder = CSVExporter.ensure_measurements_folder()
        return CSVExporter.generate_filename(prefix=prefix, folder=folder)

    def start_measurement_from_program(self, sampling_interval_ms=None):
        """ProgramRunner-compatible measurement start."""
        if sampling_interval_ms is not None:
            self.set_sampling_interval_ms(sampling_interval_ms)
        self.start_measurement()

    def stop_measurement_from_program(self):
        """ProgramRunner-compatible measurement stop."""
        self.stop_measurement()

    def sample_once(self):
        """Read one sample and notify plots/widgets."""
        sample = self.measurement_sampler.sample(
            target_pressure=self.target_pressure,
            offset=self.offset,
            rotary_active=self.rotary_active_port or None,
        )
        if sample is None:
            if not self._sample_failure_logged:
                message = "[v3] Sampling skipped: internal pressure monitor did not return a value."
                self.append_log(message)
                self.sample_failed.emit(message)
                self._sample_failure_logged = True
            self._emit_status()
            return None

        self._sample_failure_logged = False
        self.sample_ready.emit(sample)
        self._emit_status()
        return sample

    def set_target_pressure_mbar(self, value_mbar):
        """Set user-facing pressure target and send offset-corrected hardware command."""
        value_mbar = float(value_mbar)
        self.target_pressure = value_mbar
        if self.pressure_source is None:
            self.append_log("[v3] Pressure controller is not connected.")
            self._emit_status()
            return value_mbar
        self.pressure_source.setDesiredPressure(value_mbar + self.offset)
        self._emit_status()
        return value_mbar

    def set_program_pressure_command_mbar(self, display_target_mbar, hardware_target_mbar):
        """ProgramRunner-compatible closed-loop pressure command."""
        self.target_pressure = float(display_target_mbar)
        if self.pressure_source is None:
            self.append_log("[v3] Pressure controller is not connected.")
            return self.target_pressure
        self.pressure_source.setDesiredPressure(float(hardware_target_mbar) + self.offset)
        self._emit_status()
        return self.target_pressure

    def get_target_pressure_mbar(self):
        """Return the current user-facing pressure target."""
        return float(self.target_pressure)

    def reset_pressure_hardware_zero_mbar(self):
        """Send a raw 0 mbar setpoint for reset and stop-all paths."""
        if self.pressure_source is not None:
            self.pressure_source.setDesiredPressure(0)
        else:
            self.append_log("[v3] Pressure controller is not connected.")
        self.target_pressure = 0.0
        self._emit_status()

    def zero_offset_from_internal_pressure(self, persist=True):
        """Set the pressure offset from the internal pressure monitor."""
        measured = self.read_internal_pressure_mbar()
        if measured is None:
            self.append_log("[v3] Cannot zero offset: internal pressure monitor is not readable.")
            return None
        self.set_offset_mbar(measured, persist=persist, ignore_persist_errors=True)
        self.append_log(f"[v3] Pressure offset set from internal monitor: {measured:.3f} mbar")
        return measured

    def set_offset_mbar(self, offset_mbar, persist=False, ignore_persist_errors=False):
        """Update the pressure offset, optionally persisting it."""
        self.offset = float(offset_mbar)
        if persist:
            try:
                saved = save_pressure_offset(self.offset)
                if not saved:
                    self.append_log("[v3] Pressure offset could not be saved to preferences.")
            except Exception as exc:
                self.append_log(f"[v3] Pressure offset persistence failed: {exc}")
                if not ignore_persist_errors:
                    raise
        self._emit_status()
        return self.offset

    def read_internal_pressure_mbar(self):
        """Read the internal pressure monitor and convert it to mbar."""
        if self.pressure_source is None:
            return None
        raw = self.pressure_source.getRawMonitorValue()
        if raw is None:
            return None
        return self.pressure_source.bitToMbar(raw)

    def read_flow_sensor_value(self, sensor_name):
        """ProgramRunner-compatible flow read."""
        return self.runtime_devices.read_flow_sensor_value(sensor_name)

    def read_fluigent_sensor_value(self, sensor_name):
        """ProgramRunner-compatible Fluigent read."""
        return self.runtime_devices.read_fluigent_sensor_value(sensor_name)

    def get_fluigent_sensor_by_name(self, sensor_name):
        """ProgramRunner-compatible Fluigent lookup."""
        return self.runtime_devices.get_fluigent_sensor_by_name(sensor_name)

    def read_program_sensor_value(self, sensor_name):
        """Read any sensor name used by automation programs."""
        return self.runtime_devices.read_sensor_value(sensor_name, self.read_internal_pressure_mbar)

    def zero_fluigent_sensors_by_name(self, selected_sns=None):
        """Zero selected Fluigent sensors by serial/name."""
        return self.runtime_devices.zero_fluigent_sensors_by_name(selected_sns)

    def set_valve_state_by_name(self, valve_name, state, available_valves=None):
        """Set a valve using an editor-visible name."""
        ok = self.runtime_devices.set_valve_state_by_name(valve_name, state, available_valves)
        self._emit_status()
        return ok

    def set_valve_state_by_index(self, index, state):
        """Set a valve by runtime index."""
        valve = self.runtime_devices.set_valve_state_by_index(index, state)
        self._emit_status()
        return valve

    def close_all_valves(self):
        """Close every configured valve."""
        self.runtime_devices.close_all_valves()
        self._emit_status()

    def export_csv(self, path: str | None = None) -> str:
        """Export the current measurement session to CSV and return the path."""
        if path is None:
            path = self.suggest_csv_path()

        snapshot = self.measurement_session.snapshot_for_export(
            self.sampling_interval_ms,
            self.timebase.start_timestamp,
        )
        snapshot.with_metadata(
            offset=self.offset,
            valve_names=[meta["editor_name"] for meta in self._valve_meta] if self._valve_meta else None,
            profile_name=self.hw_profile.get("name"),
            valve_coils=[meta["coil"] for meta in self._valve_meta] if self._valve_meta else None,
        )
        CSVExporter.write_measurement_csv(
            path,
            time_data=snapshot.time_data,
            target=snapshot.target_data,
            corrected=snapshot.corrected_data,
            measured=snapshot.measured_data,
            valve_states=snapshot.valve_states,
            flow_data=snapshot.flow_data,
            fluigent_data=snapshot.fluigent_data,
            offset=snapshot.offset,
            sampling_interval_ms=snapshot.sampling_interval_ms,
            start_timestamp=snapshot.start_timestamp,
            rotary_active=snapshot.rotary_active,
            valve_names=snapshot.valve_names,
            profile_name=snapshot.profile_name,
            valve_coils=snapshot.valve_coils,
            fluigent_sensors=self.fluigent_sensors,
            extra_series=snapshot.extra_series,
        )
        self.append_log(f"[v3] CSV export saved to:\n{path}")
        return path

    def export_csv_from_program(self, path):
        """ProgramRunner-compatible export endpoint."""
        return self.export_csv(path)

    def load_program(self, path: str) -> bool:
        """Load a JSON automation program into the runner."""
        return self.program_runner.load_program(path)

    def run_program_from_path(self, path: str) -> bool:
        """Load and run an automation program in a Qt6 worker thread."""
        if self.program_thread_is_running():
            self.append_log("[v3] Program already running.")
            return False
        if not isinstance(path, str) or not os.path.isfile(path):
            self.append_log(f"[v3] Program file not found: {path}")
            return False
        if not self.load_program(path):
            return False

        self.program_thread = QThread(self)
        self.program_worker = V3ProgramWorker(self.program_runner)
        self.program_worker.moveToThread(self.program_thread)
        self.program_thread.started.connect(self.program_worker.run)
        self.program_worker.log_message.connect(self.append_log)
        self.program_worker.error.connect(self._handle_program_error)
        self.program_worker.stopped.connect(self.append_log)
        self.program_worker.finished.connect(self.program_thread.quit)
        self.program_worker.finished.connect(self.program_worker.deleteLater)
        self.program_thread.finished.connect(self.program_thread.deleteLater)
        self.program_thread.finished.connect(self._clear_program_thread_refs)
        self.program_thread.start()
        self.program_state_changed.emit(True)
        self._emit_status()
        return True

    def stop_program(self) -> None:
        """Stop the currently running automation program."""
        if not self.program_thread_is_running() and self.program_worker is None:
            self.program_runner.stop()
            self._emit_status()
            return

        self.append_log("[v3] Program stop requested.")
        try:
            self.program_runner.stop()
        except Exception as exc:
            self.append_log(f"[v3] Program runner stop failed: {exc}")
        if self.program_worker is not None:
            try:
                self.program_worker.stop()
            except RuntimeError:
                # The worker may already be finishing; the runner stop flag above is the important part.
                pass
            except Exception as exc:
                self.append_log(f"[v3] Program worker stop failed: {exc}")
        self._emit_status()

    def set_rotary_adapter(self, adapter) -> None:
        """Attach the v3 rotary valve card for UI and automation access."""
        self.rotary_adapter = adapter
        try:
            self.runtime_devices.set_rotary_widget(adapter)
            self.refresh_rotary_catalog_state()
        except Exception as exc:
            self.append_log(f"[v3] Rotary catalog registration failed: {exc}")

    def refresh_rotary_catalog_state(self) -> None:
        """Refresh rotary valve catalog metadata after connection-state changes."""
        self.runtime_devices.register_rotary_valve()
        self._publish_device_catalog()
        self._emit_status()

    def set_rotary_active_port(self, port: int | None) -> None:
        """Store the last known active rotary port for sampling and CSV export."""
        try:
            self.rotary_active_port = int(port or 0)
        except Exception:
            self.rotary_active_port = 0

    def program_thread_is_running(self) -> bool:
        """Return True while a program thread is active."""
        thread = self.program_thread
        try:
            return bool(thread is not None and thread.isRunning())
        except RuntimeError:
            return False

    def _handle_program_error(self, message: str) -> None:
        """Forward worker errors to UI logs and status."""
        self.program_error.emit(message)
        self.append_log(message)

    def _clear_program_thread_refs(self) -> None:
        """Drop stale worker references after completion."""
        self.program_thread = None
        self.program_worker = None
        self.program_state_changed.emit(False)
        self.program_finished.emit()
        self._emit_status()

    def ensure_rotary_connected_from_program(self):
        """Connect the v3 rotary valve adapter if needed."""
        if self.rotary_adapter is None:
            raise RuntimeError("Rotary valve UI is not available.")
        rotary = self.rotary_adapter.rotary
        if rotary.is_connected():
            return True
        port = ""
        try:
            port = self.rotary_adapter.com.currentText().strip()
        except Exception:
            port = ""
        port = port or load_last_comport("rotary_valve") or ""
        if not port:
            raise RuntimeError("No rotary valve COM port is selected.")
        rotary.connect(port, 12)
        return True

    def get_rotary_state_from_program(self):
        """Return `(num_ports, current_port)` for automation rotary actions."""
        self.ensure_rotary_connected_from_program()
        rotary = self.rotary_adapter.rotary
        return rotary.num_ports(), rotary.position()

    def home_rotary_from_program(self):
        """Home the v3 rotary valve adapter."""
        self.ensure_rotary_connected_from_program()
        self.rotary_adapter.rotary.home(wait=True)
        self.set_rotary_active_port(self.rotary_adapter.rotary.position())

    def goto_rotary_from_program(self, target, wait=True):
        """Move the v3 rotary valve adapter to a target port."""
        self.ensure_rotary_connected_from_program()
        self.rotary_adapter.rotary.goto(int(target), wait=wait)
        self.set_rotary_active_port(self.rotary_adapter.rotary.position())
