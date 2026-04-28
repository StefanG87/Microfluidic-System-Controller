# modules/gui_window.py
import os
import sys
from collections import deque
import time
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer, QThread, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLineEdit, QLabel,
    QToolButton, QGroupBox, QTextEdit, QFileDialog,
    QMessageBox, QInputDialog, QApplication, QDialog,
)
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence
from pymodbus.client import ModbusTcpClient

from modules.pressure_controller import PressureController
from modules.valve import Valve
from modules.plot_area import PlotArea
from modules.export_dialog import ExportDialog
from modules.sampling_manager import SamplingDialog, sampling_manager
from modules.flow_sensor import SensirionFlowSensor
from modules.measurement_session import MeasurementSession
from modules.measurement_sampler import MeasurementSampler
from modules.device_catalog import (
    SENSOR_NAME_INTERNAL,
    UNIT_FLOW_UL_MIN,
    UNIT_PRESSURE_MBAR,
    valve_meta_from_profile_item,
)
from modules.fluigent_wrapper import detect_fluigent_sensors
from modules.runtime_devices import RuntimeDeviceRegistry
from modules.program_runner import ProgramRunner
from modules.program_worker import ProgramWorker
from editor.modules.editor.task_globals import update_available_sensors, update_available_valves
from modules.rotary_valve_widget import RotaryValveQBox
from modules.mf_common import (
    log_error, log_info, load_pressure_offset, save_pressure_offset,
    load_last_modbus_ip, save_last_modbus_ip, load_hardware_profile,
    load_hw_profile_from_prefs, save_hw_profile_to_prefs, list_hw_profiles,
    load_last_comport, save_last_comport, resource_path,
)
from modules.rvm_dt import list_serial_ports


class _GuiCallInvoker(QtCore.QObject):
    """Signal bridge for running worker-thread requests on the Qt GUI thread."""

    call_requested = QtCore.pyqtSignal(object)


class PressureFlowGUI(QWidget):
    def __init__(self):
        super().__init__()
       
        self.program_thread = None
        self.program_worker = None
        self._gui_call_invoker = _GuiCallInvoker(self)
        self._gui_call_invoker.call_requested.connect(self._execute_gui_call, Qt.QueuedConnection)

        self.setWindowTitle("Microfluidic System Controller")
        
        # --- Initial state ---
        self.offset = load_pressure_offset() 
        self.target_pressure = 0.0
        self.is_measuring = False
        self.start_timestamp = None
        self.sampling_interval_ms = 250
        self.sampling_rate = self.sampling_interval_ms  # Legacy alias for older helpers.
        sampling_manager.set_sampling_interval_ms(self.sampling_interval_ms)
        sampling_manager.reset_time()
        
        # make the GUI globally available for sampling_manager & dialogs
        app = QApplication.instance()
        if app is not None:
            app.main_window = self
        
    
        # --- Measurement buffers ---
        self.measurement_session = MeasurementSession(flow_channel_count=4)
        self._bind_measurement_buffers()
        self.runtime_devices = RuntimeDeviceRegistry()
        self.device_catalog = self.runtime_devices.catalog
        self.measurement_sampler = MeasurementSampler(
            self.runtime_devices,
            self.measurement_session,
            sampling_manager,
        )
    
        # --- Connect to Modbus ---
        try:
            self.modbus = self._connect_modbus_auto()
        except Exception as e:
            # Show a clear message and exit cleanly.
            QMessageBox.critical(self, "Connection Error", str(e))
            sys.exit(1)
    
        # --- Initialize runtime components ---
        self.pressure_source = PressureController(self.modbus, register=1, type=2)
        self.runtime_devices.set_pressure_source(self.pressure_source)
        self.runtime_devices.register_pressure_controller()
        
        # --- Load the hardware profile from device_prefs.json ---
        profile_name = load_hw_profile_from_prefs(default="stand1")
        self.hw_profile = load_hardware_profile(profile_name)
        
        # --- Build valves from the profile and publish editor/runner names ---
        self._build_valves_from_profile()

        # Mapping: valve object -> associated QPushButton.
        self._valve_btn_by_valve = {}

        # --- Flow sensors ---
        self.flow_sensors = [
            SensirionFlowSensor(
                self.modbus, register=4 + i,
                name=f"Flow {i+1}",
                v_min=0.0, v_max=10.0,
                flow_min=0.0, flow_max=1000.0
            )
            for i in range(4)
        ]
        self.measurement_session.set_flow_channel_count(len(self.flow_sensors))
        self.runtime_devices.set_flow_sensors(self.flow_sensors)
        self.runtime_devices.register_flow_sensors()
        
        # --- Fluigent sensors ---
        self.fluigent_sensors = detect_fluigent_sensors()
        self.measurement_session.set_fluigent_channel_count(len(self.fluigent_sensors))
        self._bind_measurement_buffers()
        self.runtime_devices.set_fluigent_sensors(self.fluigent_sensors)
        self.runtime_devices.register_fluigent_sensors()

        
        # --- Prepare display widgets ---
        self.sensor_labels = {}  # Live labels for sensor values.
        
        self.log_lines = []  # Optional cache for later persistence.

        # --- Rotary Valve ---
        self.rotaryBox = RotaryValveQBox(self)
        self.rotary_active = self.measurement_session.rotary_active  # per-sample active rotary port.
        
        self.rotary_is_busy = False
        self.rotary_last_port = None
        
        # --- Rotary active-time series for plot bands ---
        self._t0_monotonic = time.monotonic()   # reference for relative seconds
        self.rotary_events = deque(maxlen=20000)  # list of (t_rel_s: float, port: int|0)
        
        # Connect the single rotary signal path used by plot bands and movement gaps.
        self.rotaryBox.activeChanged.connect(self._on_rv_active_changed)
        
        self.rotaryBox.movedStarted.connect(self._on_rv_started)
        self.rotaryBox.movedFinished.connect(self._on_rv_finished)
        self.runtime_devices.set_rotary_widget(self.rotaryBox)
        self.runtime_devices.register_rotary_valve()
        self._publish_device_catalog()

        # --- Prepare program execution ---
        self.program_runner = ProgramRunner(self)
        
        self.log_visible = True  # Set to False to start with the log hidden.
        self.favorite_widgets = []  # Row layouts for the favorite-program slots.


    
        # --- Start the periodic update timer ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(self.sampling_interval_ms)
        
    
        # --- Build the UI ---
        self.build_ui()

        # --- Keyboard shortcuts ---
        # Ctrl+S -> open the CSV export dialog.
        QShortcut(QKeySequence.Save, self, activated=lambda: self.do_csv_export(path=None, silent=False))
        
        # Enter/Return -> trigger "Set Pressure" just like the button.
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=self.set_pressure)
        QShortcut(QKeySequence(Qt.Key_Enter),  self, activated=self.set_pressure)
        
        # Esc -> close the window and trigger closeEvent for a safe shutdown.
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)


    def _execute_gui_call(self, request):
        """Execute a queued worker-thread request on the GUI thread."""
        fn, done, result = request
        try:
            result["value"] = fn()
        except Exception as exc:
            result["error"] = exc
        finally:
            done.set()

    def _call_in_gui_thread(self, fn):
        """Run `fn` on the GUI thread and return its result to the caller."""
        if QtCore.QThread.currentThread() == self.thread():
            return fn()

        from threading import Event

        done = Event()
        result = {}
        self._gui_call_invoker.call_requested.emit((fn, done, result))
        done.wait()
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def _bind_measurement_buffers(self):
        """Expose measurement-session buffers through the legacy GUI attributes."""
        session = self.measurement_session
        self.time_data = session.time_data
        self.target_data = session.target_data
        self.corrected_data = session.corrected_data
        self.measured_data = session.measured_data
        self.valve_states = session.valve_states
        self.flow_data = session.flow_data
        self.fluigent_pressure_data = session.fluigent_pressure_data
        self.abs_time_data = session.abs_time_data
        self.rotary_active = session.rotary_active

    def _publish_device_catalog(self) -> None:
        """Publish current runtime devices to editor globals without duplicating lists."""
        update_available_valves(self.device_catalog.valve_names())
        self.available_sensors = self.device_catalog.sensor_names()
        update_available_sensors(self.available_sensors)

    def _refresh_sensor_value_labels(self) -> None:
        """Rebuild the live sensor-value labels from the runtime device catalog."""
        if not hasattr(self, "sensor_layout"):
            return

        while self.sensor_layout.count():
            item = self.sensor_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.sensor_labels = {}
        for sensor in self.device_catalog.sensors():
            suffix = f" {sensor.unit}" if sensor.unit else ""
            label = QLabel(f"{sensor.name}: --{suffix}")
            self.sensor_labels[sensor.name] = label
            self.sensor_layout.addWidget(label)

    def update_device_config(self) -> None:
        """Refresh detectable devices without changing active hardware output states."""
        if self.is_measuring or self.program_thread is not None:
            QMessageBox.warning(
                self,
                "Config Update",
                "Stop the current measurement or program before updating the device config.",
            )
            return

        try:
            refresh_result = self.runtime_devices.refresh_detectable_devices(
                self.read_internal_pressure_mbar,
                detect_fluigent_sensors,
            )
            self.fluigent_sensors = self.runtime_devices.fluigent_sensors

            self.measurement_session.set_fluigent_channel_count(len(self.fluigent_sensors))
            self._bind_measurement_buffers()
            self._publish_device_catalog()
            self._refresh_sensor_value_labels()

            if hasattr(self, "plot_area"):
                if hasattr(self.plot_area, "refresh_fluigent_sensors"):
                    self.plot_area.refresh_fluigent_sensors(
                        self.fluigent_sensors,
                        self.fluigent_pressure_data,
                    )
                else:
                    self.plot_area.fluigent_sensors = self.fluigent_sensors
                    self.plot_area.fluigent_pressure_data = self.fluigent_pressure_data

            message = f"Device config refreshed ({refresh_result.summary})."
            self.append_log(message)
            QMessageBox.information(self, "Config Update", message)
        except Exception as e:
            log_error(f"Device config refresh failed: {e}", display_ui=True, parent=self)

    def _connect_modbus_auto(self) -> ModbusTcpClient:
        """
        Try to connect to a Modbus-TCP device by testing a list of candidate IPs.
        Order:
          1) Last known IP (stored in settings.json)
          2) Environment variable MF_MODBUS_IPS (comma separated)
          3) Common defaults (192.168.1.100, 192.168.0.100, 192.168.1.10, 192.168.1.50)
        If all fail, prompt user for an IP and retry once. Shows message boxes on failure.
        """
        tried = []
    
        # 1) last known
        candidates = []
        last_ip = load_last_modbus_ip()
        if last_ip:
            candidates.append(last_ip)
    
        # 2) env list
        env_ips = os.environ.get("MF_MODBUS_IPS", "")
        if env_ips.strip():
            for ip in env_ips.split(","):
                ip = ip.strip()
                if ip and ip not in candidates:
                    candidates.append(ip)
    
        # 3) common defaults
        for ip in ["192.168.1.100", "192.168.0.100", "192.168.1.10", "192.168.1.50"]:
            if ip not in candidates:
                candidates.append(ip)
    
        # Try helper
        def _try_connect(ip: str):
            client = ModbusTcpClient(ip, port=502, timeout=1.2)
            ok = False
            try:
                ok = client.connect()
            except Exception:
                ok = False
            if ok:
                save_last_modbus_ip(ip)
                log_info(f"[Modbus] Connected to {ip}")
                return client
            try:
                client.close()
            except Exception:
                pass
            tried.append(ip)
            return None
    
        # Try all candidates
        for ip in candidates:
            cli = _try_connect(ip)
            if cli:
                return cli
    
        # If nothing worked, ask the user once
        ip, ok = QInputDialog.getText(
            self, "Connect Modbus",
            "No Modbus device auto-detected.\n"
            "Enter device IP (e.g. 192.168.1.100):"
        )
        if ok and ip and ip.strip():
            cli = _try_connect(ip.strip())
            if cli:
                return cli
            QMessageBox.critical(
                self, "Connection Error",
                f"Could not connect to Modbus at {ip.strip()} (port 502).\n"
                f"Tried also: {', '.join(tried)}"
            )
            raise RuntimeError(f"Modbus connection failed for {ip.strip()}")
    
        # user cancelled
        raise RuntimeError("Modbus connection aborted by user.")

    def _build_valves_from_profile(self) -> None:
        """Build valve objects, metadata, and editor catalogs from the active profile."""
        self.valves = []
        self._valve_meta = []
        for group in self.hw_profile.get("valve_groups", []):
            for item in group.get("items", []):
                v = Valve(self.modbus, int(item["coil"]))
                self.valves.append(v)
                meta = valve_meta_from_profile_item(group, item)
                self._valve_meta.append(meta)
        self.runtime_devices.set_valves(self.valves, self._valve_meta)
        self.runtime_devices.register_valves()
    
        # Publish the editor-visible valve names in the same order used by the GUI.
        update_available_valves(self.device_catalog.valve_names())

    
    def _clear_valve_groups(self) -> None:
        """Remove the existing valve group widgets from the left control column."""
        if not hasattr(self, "_valve_group_widgets"):
            self._valve_group_widgets = []
        for w in self._valve_group_widgets:
            try:
                self.control_layout.removeWidget(w)
                w.setParent(None)
                w.deleteLater()
            except Exception:
                pass
        self._valve_group_widgets.clear()
        if hasattr(self, "_valve_btn_by_valve"):
            self._valve_btn_by_valve.clear()
    
    
    def _add_valve_groups(self) -> None:
        """Create valve group widgets from the active profile and add them to the control layout."""
        if not hasattr(self, "_valve_group_widgets"):
            self._valve_group_widgets = []
    
        for group in self.hw_profile.get("valve_groups", []):
            items = []
            for m, v in zip(self._valve_meta, self.valves):
                if m.get("box") == group.get("box"):
                    items.append((m["button_label"], v))
            if items:
                box = self.create_valve_group(group.get("box", "Valves"), items)
                self.control_layout.addWidget(box)
                self._valve_group_widgets.append(box)
    
    
    def switch_hw_profile(self, name: str) -> None:
        """
        Persist the selected profile, reload it, and rebuild valves and valve groups.
        """
        if save_hw_profile_to_prefs(name):
            self.hw_profile = load_hardware_profile(name)
            self._clear_valve_groups()
            self._build_valves_from_profile()
            names = [m["editor_name"] for m in self._valve_meta]
            if hasattr(self.plot_area, "set_valve_names"):
                self.plot_area.set_valve_names(names)
            try:
                self.plot_area.update_plot()
            except Exception:
                pass

            self._add_valve_groups()
            try:
                self.append_log(f"Hardware profile switched to '{name}'.")
            except Exception:
                pass



    def build_ui(self):
        layout = QHBoxLayout(self)
    
        # === Left column ===
        control_layout = QVBoxLayout()
        self.control_layout = control_layout  # Store for later dynamic valve-group rebuilds.

        # --- Top toolbar ---
        toolbar = QHBoxLayout()
        
        self.btn_zero = QToolButton()
        self.btn_zero.setIcon(QIcon(resource_path("icons/zero.png")))
        self.btn_zero.setToolTip("Calibrate pressure to 0")
        self.btn_zero.clicked.connect(self.choose_zero_method)
        toolbar.addWidget(self.btn_zero)
        
        self.btn_zero_fluigent = QPushButton("Zero Fluigent Sensors")
        self.btn_zero_fluigent.clicked.connect(self.zero_fluigent_sensors)
        toolbar.addWidget(self.btn_zero_fluigent)
        
        self.btn_set0 = QPushButton("Set Pressure to 0")
        self.btn_set0.clicked.connect(self.reset_pressure_hardware_zero_mbar)
        toolbar.addWidget(self.btn_set0)
        
        self.btn_export = QToolButton()
        self.btn_export.setIcon(QIcon(resource_path("icons/csv.png")))
        self.btn_export.setToolTip("Export CSV")
        self.btn_export.clicked.connect(self.export_csv)
        toolbar.addWidget(self.btn_export)
        
        self.btn_sampling = QToolButton()
        self.btn_sampling.setIcon(QIcon(resource_path("icons/sampling.png")))
        self.btn_sampling.setToolTip("Set sampling interval")
        self.btn_sampling.clicked.connect(self.open_sampling_dialog)
        toolbar.addWidget(self.btn_sampling)

        self.btn_update_config = QPushButton("Update Config")
        self.btn_update_config.setToolTip("Refresh detected sensors and editor device lists")
        self.btn_update_config.clicked.connect(self.update_device_config)
        toolbar.addWidget(self.btn_update_config)
        
        # --- Profile selector on the right side of the toolbar ---
        from PyQt5.QtWidgets import QComboBox
        self.cmb_profile = QComboBox()
        profiles = list_hw_profiles() or ["stand1", "stand1"]
        self.cmb_profile.addItems(profiles)
        
        try:
            curr = self.hw_profile.get("name") or load_hw_profile_from_prefs(default="stand1")
        except Exception:
            curr = load_hw_profile_from_prefs(default="stand1")
        idx = self.cmb_profile.findText(str(curr))
        if idx >= 0:
            self.cmb_profile.setCurrentIndex(idx)
        
        def _on_profile_changed():
            name = self.cmb_profile.currentText().strip()
            if name:
                self.switch_hw_profile(name)
        
        self.cmb_profile.currentIndexChanged.connect(_on_profile_changed)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Profile:"))
        toolbar.addWidget(self.cmb_profile)

        
        # Add the toolbar to the control layout.
        control_layout.addLayout(toolbar)

            
    
        # --- Pressure control ---
        self.input_pressure = QLineEdit()
        self.input_pressure.setPlaceholderText("Target pressure [mbar]")
        control_layout.addWidget(self.input_pressure)
    
        btn_set = QPushButton("Set Pressure")
        btn_set.clicked.connect(self.set_pressure)
        control_layout.addWidget(btn_set)
    
        self.btn_start = QPushButton("Start Measurement")
        self.btn_start.clicked.connect(self.start_measurement)
        control_layout.addWidget(self.btn_start)
    
        self.btn_stop = QPushButton("Stop Measurement")
        self.btn_stop.clicked.connect(self.stop_measurement)
        control_layout.addWidget(self.btn_stop)
    
        self.label_display = QLabel("Measured: -- mbar | Corrected: -- mbar")
        control_layout.addWidget(self.label_display)
    
        # --- Add valve groups from the active profile ---
        self._add_valve_groups()


        # --- Rotary Valve ---
        control_layout.addWidget(self.rotaryBox)
    
        # --- Sensor values ---
        self.sensor_labels = {}
        self.sensor_display = QGroupBox("Sensor Values")
        self.sensor_layout = QVBoxLayout()
        self._refresh_sensor_value_labels()
    
        self.sensor_display.setLayout(self.sensor_layout)
        control_layout.addWidget(self.sensor_display)
    
        # === Program controls ===
        self.program_group = QGroupBox("Program Control")
        program_layout = QVBoxLayout()

        # === Favorites ===
        self.program_favorites = [None] * 5
        self.favorite_labels = []
        self.favorite_select_buttons = []
        self.favorite_run_buttons = []
        
        for i in range(5):
            row = QHBoxLayout()
        
            label = QLabel("No file selected")
            label.setStyleSheet("color: gray;")
            self.favorite_labels.append(label)
            row.addWidget(label, 1)
        
            btn_select = QPushButton("...")
            btn_select.setFixedWidth(45)
            btn_select.clicked.connect(lambda _, idx=i: self.select_favorite(idx))
            self.favorite_select_buttons.append(btn_select)
            row.addWidget(btn_select)
        
            btn_run = QPushButton("Run")
            btn_run.setFixedWidth(45)
            btn_run.clicked.connect(lambda _, idx=i: self.run_favorite(idx))
            self.favorite_run_buttons.append(btn_run)
            row.addWidget(btn_run)
        
            program_layout.addLayout(row)


    
        self.btn_open_editor = QPushButton("Open Program Editor")
        self.btn_open_editor.clicked.connect(self.open_editor)
        program_layout.addWidget(self.btn_open_editor)
    
        self.btn_run_program = QPushButton("Load & Run Program")
        self.btn_run_program.clicked.connect(self.open_program_dialog_and_run)
        program_layout.addWidget(self.btn_run_program)
    
        self.btn_stop_program = QPushButton("Stop Program")
        self.btn_stop_program.clicked.connect(self.stop_program)
        self.btn_stop_program.setEnabled(False)
        program_layout.addWidget(self.btn_stop_program)
    
        self.btn_toggle_log = QPushButton("Hide Log")
        self.btn_toggle_log.clicked.connect(self.toggle_log_display)
        program_layout.addWidget(self.btn_toggle_log)
    
        self.program_group.setLayout(program_layout)
        control_layout.addWidget(self.program_group)
    
        control_layout.addStretch()
        layout.addLayout(control_layout, 1)
    
        # === Right side: plot and log ===
        right_layout = QVBoxLayout()
    
        self.plot_area = PlotArea(
            self, self.time_data, self.target_data,
            self.corrected_data, self.measured_data,
            self.valve_states, self.flow_data, self.fluigent_pressure_data,
            self.fluigent_sensors,
            rotary_active=self.rotary_active
        )
        right_layout.addWidget(self.plot_area, 3)
    
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setPlaceholderText("Program log...")
        self.log_display.setMinimumHeight(100)
        self.log_display.setVisible(self.log_visible)  # Show only when the log panel is enabled.
        right_layout.addWidget(self.log_display, 1)
    
        layout.addLayout(right_layout, 2)

        # Initialize the plot labels from the active hardware profile.
        names = [m["editor_name"] for m in self._valve_meta]
        if hasattr(self.plot_area, "set_valve_names"):
            self.plot_area.set_valve_names(names)


    def create_valve_group(self, title, items):
        """
        items: List[Tuple[str button_label, Valve valve_obj]]
        """
        group = QGroupBox(title)
        grid = QGridLayout()
        for i, (label, valve) in enumerate(items):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, v=valve, b=btn: self.toggle_valve(v, b))
            grid.addWidget(btn, i // 2, i % 2)
    
            self._valve_btn_by_valve[valve] = btn
            btn.setChecked(bool(valve.get_state()))
        group.setLayout(grid)
        return group

    def toggle_valve(self, valve, button):
        valve.toggle()
        button.setChecked(valve.get_state())

    def choose_zero_method(self):
        options = ["Use Pressure Controller (raw)", "Calibrate using Fluigent Sensor"]
        choice, ok = QInputDialog.getItem(self, "Zero Method", "Choose calibration method:", options, 0, False)
        if ok:
            if choice == options[0]:
                self.set_zero_pressure()
            elif choice == options[1]:
                self.choose_fluigent_sensor()

    def set_zero_pressure(self):
        val = self.pressure_source.getRawMonitorValue()
        if val is not None:
            self.offset = self.pressure_source.bitToMbar(val)
            QMessageBox.information(self, "Offset", f"Offset set to {self.offset:.2f} mbar")
            self._persist_offset() 

    def choose_fluigent_sensor(self):
        """Select one Fluigent sensor and calibrate the pressure offset from it."""
        if not self.fluigent_sensors:
            QMessageBox.warning(self, "No Sensors", "No Fluigent sensors available.")
            return

        # Present the available Fluigent sensor serial numbers.
        items = [f"SN{sensor.device_sn}" for sensor in self.fluigent_sensors]
        sensor_choice, ok = QInputDialog.getItem(self, "Select Fluigent Sensor", "Sensor:", items, 0, False)
        if ok:
            index = items.index(sensor_choice)
            self.calibrate_from_fluigent(index)

    def calibrate_from_fluigent(self, sensor_index):
        """Set the offset so the corrected pressure matches the selected Fluigent sensor."""
        try:
            sensor = self.fluigent_sensors[sensor_index]
            fluigent_val = sensor.read_pressure()
            raw_val = self.pressure_source.getRawMonitorValue()
            if fluigent_val is not None and raw_val is not None:
                measured = self.pressure_source.bitToMbar(raw_val)
                self.offset = measured - fluigent_val
                # Include the sensor serial number in the confirmation message.
                QMessageBox.information(
                    self, "Offset",
                    f"Offset set so that corrected = {fluigent_val:.2f} mbar (SN{sensor.device_sn})"
                )
                self._persist_offset()
            else:
                QMessageBox.warning(self, "Error", "Could not read from sensor(s).")
        except IndexError:
            QMessageBox.warning(self, "Error", "Selected Fluigent sensor not available.")
    
    def zero_fluigent_sensors(self):
        """
        Open the selection dialog and run hardware zeroing for the chosen sensors.
        """
        from modules.sensor_zero_dialog import SensorZeroDialog
        from Fluigent.SDK import fgt_set_sensorCalibration
    
        dialog = SensorZeroDialog(self.fluigent_sensors, parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
    
        self.timer.stop()
        print("[Fluigent] Update loop paused for sensor zeroing.")
    
        try:
            for sensor in dialog.selected_sensors:
                err = fgt_set_sensorCalibration(sensor.index, 1)
                if err != 0:
                    print(f"[Fluigent] Zeroing failed for SN {sensor.device_sn} (Index {sensor.index}) -> code {err}")
                else:
                    print(f"[Fluigent] Sensor SN {sensor.device_sn} (Index {sensor.index}) zeroed")
        except Exception as e:
            print(f"[Fluigent] Zeroing error: {e}")
        finally:
            self.timer.start(self.sampling_interval_ms)
            print("[Fluigent] Update loop resumed.")
    
        QMessageBox.information(self, "Zero", f"{len(dialog.selected_sensors)} sensor(s) zeroed successfully.")

    def _persist_offset(self):
        """
        Save current self.offset to JSON and refresh any UI text that shows it.
        """
        ok = save_pressure_offset(self.offset)
        if not ok:
            QMessageBox.warning(self, "Offset", "Saving the offset failed.")

    def set_target_pressure_mbar(self, value_mbar):
        """Set the user-facing pressure target and send the offset-corrected setpoint."""
        value_mbar = float(value_mbar)
        self.target_pressure = value_mbar
        self.pressure_source.setDesiredPressure(value_mbar + self.offset)
        return value_mbar

    def set_program_pressure_command_mbar(self, display_target_mbar, hardware_target_mbar):
        """Set separate displayed and hardware pressure targets for automation control loops."""
        display_target_mbar = float(display_target_mbar)
        hardware_target_mbar = float(hardware_target_mbar)
        self.target_pressure = display_target_mbar
        self.pressure_source.setDesiredPressure(hardware_target_mbar + self.offset)
        return display_target_mbar

    def get_target_pressure_mbar(self):
        """Return the current user-facing pressure target in mbar."""
        return float(getattr(self, "target_pressure", 0.0))

    def reset_pressure_hardware_zero_mbar(self):
        """Send a raw 0 mbar hardware setpoint for reset/stop-all paths."""
        self.pressure_source.setDesiredPressure(0)
        self.target_pressure = 0.0

    def set_offset_mbar(self, offset_mbar, persist=False, ignore_persist_errors=False):
        """Update the pressure offset, optionally persisting it to disk."""
        self.offset = float(offset_mbar)
        if persist:
            if ignore_persist_errors:
                try:
                    self._persist_offset()
                except Exception:
                    pass
            else:
                self._persist_offset()
        return self.offset

    def read_internal_pressure_mbar(self):
        """Read the internal pressure monitor and convert it to mbar."""
        raw = self.pressure_source.getRawMonitorValue()
        if raw is None:
            return None
        return self.pressure_source.bitToMbar(raw)

    def get_fluigent_sensor_by_name(self, sensor_name):
        """Return the Fluigent sensor matching an editor-visible serial name."""
        return self.runtime_devices.get_fluigent_sensor_by_name(sensor_name)

    def read_fluigent_sensor_value(self, sensor_name):
        """Read a Fluigent sensor by its editor-visible serial name."""
        return self.runtime_devices.read_fluigent_sensor_value(sensor_name)

    def zero_fluigent_sensors_by_name(self, selected_sns=None):
        """Zero selected Fluigent sensors and return successful and failed serial names."""
        return self.runtime_devices.zero_fluigent_sensors_by_name(selected_sns)

    def read_flow_sensor_value(self, sensor_name):
        """Read a flow sensor by its editor-visible channel name."""
        return self.runtime_devices.read_flow_sensor_value(sensor_name)

    def read_program_sensor_value(self, sensor_name):
        """Read any sensor name used by automation programs."""
        return self.runtime_devices.read_sensor_value(
            sensor_name,
            self.read_internal_pressure_mbar,
        )

    def set_valve_state_by_index(self, index, state):
        """Set a valve by hardware-list index without adding UI or log side effects."""
        return self.runtime_devices.set_valve_state_by_index(index, state)

    def set_valve_state_by_name(self, valve_name, state, available_valves):
        """Set a valve using the editor-visible valve order."""
        return self.runtime_devices.set_valve_state_by_name(
            valve_name,
            state,
            available_valves,
        )

    def close_all_valves(self):
        """Close every configured valve without changing pressure."""
        self.runtime_devices.close_all_valves()

    def start_measurement_from_program(self, sampling_interval_ms=None):
        """Start a measurement from an automation program without user confirmation."""
        return self._call_in_gui_thread(
            lambda: self.start_measurement(automated=True, sampling_interval_ms=sampling_interval_ms)
        )

    def stop_measurement_from_program(self):
        """Stop a measurement from an automation program without extra UI prompts."""
        return self._call_in_gui_thread(lambda: self.stop_measurement(automated=True))

    def export_csv_from_program(self, path):
        """Run the non-interactive CSV export used by automation programs."""
        return self._call_in_gui_thread(lambda: self.do_csv_export(path=path, silent=True))

    def set_pressure(self):
        try:
            value = float(self.input_pressure.text())
            self.set_target_pressure_mbar(value)
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number.")

    def set_sampling_interval_ms(self, interval_ms):
        """Apply a sampling interval in milliseconds and keep all timers in sync."""
        interval_ms = max(1, int(interval_ms))
        self.sampling_interval_ms = interval_ms
        self.sampling_rate = interval_ms  # Legacy alias for older helpers.
        sampling_manager.set_sampling_interval_ms(interval_ms)
        if hasattr(self, "timer"):
            self.timer.setInterval(interval_ms)
            if not self.timer.isActive():
                self.timer.start(interval_ms)

    def set_sampling_rate_ms(self, value_ms):
        """Backward-compatible wrapper for older code using the rate name."""
        self.set_sampling_interval_ms(value_ms)

    def start_measurement(self, automated=False, sampling_interval_ms=None, sampling_rate_hz=None):
        """Initialize a new measurement and reset the shared sampling-manager time base."""
        if not automated:
            reply = QMessageBox.question(
                self, "Start Measurement", "Clear existing data and start a new measurement?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
    
        self.is_measuring = True

        if sampling_interval_ms is None and sampling_rate_hz is not None:
            # Legacy automation programs stored this value as a frequency in Hz.
            try:
                sampling_interval_ms = max(1, int(round(1000.0 / float(sampling_rate_hz))))
            except (TypeError, ValueError, ZeroDivisionError):
                sampling_interval_ms = None

        if sampling_interval_ms is not None:
            try:
                self.set_sampling_interval_ms(sampling_interval_ms)
            except (TypeError, ValueError):
                pass
    
        # Reset the shared time base for plots and events.
        sampling_manager.reset_time()
        self.start_timestamp = sampling_manager.start_timestamp
    
        # Clear all measurement buffers for the new run.
        self.measurement_session.reset()
        
        # Reset the plot x-axis so the new run starts at 0 s.
        try:
            self.plot_area.reset_x_limits()
        except Exception:
            pass

        # Clear the rotary event stream and add the initial state at t=0.
        try:
            self.rotary_events.clear()
            p = 0
            if hasattr(self, "rotaryBox") and self.rotaryBox.ctl.is_connected():
                try:
                    p = int(self.rotaryBox.ctl.position())
                except Exception:
                    p = 0
            self.rotary_events.append((0.0, p if (p and p > 0) else 0))
            self.plot_area.set_rotary_events(self.rotary_events)
        except Exception:
            pass
    
        self.time_counter = 0.0
    
        if not automated:
            self.append_log("Manual measurement started.")


            
    def stop_measurement(self, automated=False):
        self.is_measuring = False
        if not automated:
            self.append_log("Manual measurement stopped.")
            self.export_csv()

    def _invoke_gui(self, fn):
        """Schedule a small GUI update from automation code."""
        try:
            QtCore.QTimer.singleShot(0, fn)
        except Exception:
            try:
                fn()
            except Exception:
                pass

    def _get_rotary_box(self):
        """Return the rotary-valve widget used by the main GUI."""
        box = getattr(self, "rotaryBox", None)
        if box is None:
            raise RuntimeError("Rotary Valve widget not available in GUI.")
        return box

    def _with_rotary_critical(self, fn):
        """Pause rotary polling while a blocking serial operation is running."""
        box = self._get_rotary_box()
        timer = getattr(box, "timer", None)
        was_active = bool(timer and timer.isActive())
        try:
            if was_active:
                timer.stop()
            return fn()
        finally:
            if was_active:
                timer.start()

    def ensure_rotary_connected_from_program(self):
        """Connect the rotary valve for automation using the same candidates as the GUI."""
        box = self._get_rotary_box()
        ctl = box.ctl
        if ctl.is_connected():
            return

        tried = set()
        candidates = []

        com_from_prefs = load_last_comport("rotary_valve") or ""
        if com_from_prefs and com_from_prefs not in tried:
            candidates.append(com_from_prefs)
            tried.add(com_from_prefs)

        try:
            com_from_gui = box.cmbCom.currentText().strip()
        except Exception:
            com_from_gui = ""
        if com_from_gui and com_from_gui not in tried:
            candidates.append(com_from_gui)
            tried.add(com_from_gui)

        for port_name in list_serial_ports():
            if port_name not in tried:
                candidates.append(port_name)
                tried.add(port_name)

        last_error = None
        positions = box.cmbGoto.count() or 12
        for port in candidates:
            try:
                ctl.connect(port, positions=positions)
                try:
                    save_last_comport(port, device_key="rotary_valve")
                except Exception:
                    pass
                return
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise RuntimeError("Unable to connect to the rotary valve.")

    def get_rotary_state_from_program(self):
        """Return `(num_ports, current_port)` for an automation rotary action."""
        self.ensure_rotary_connected_from_program()
        box = self._get_rotary_box()
        ctl = box.ctl
        try:
            num_ports = int(ctl.num_ports())
        except Exception:
            num_ports = int(box.cmbGoto.count() or 12)
        try:
            current_port = int(ctl.position())
        except Exception:
            current_port = 0
        return num_ports, current_port

    def home_rotary_from_program(self):
        """Home the rotary valve and synchronize the GUI signals as before."""
        self.ensure_rotary_connected_from_program()
        box = self._get_rotary_box()
        ctl = box.ctl
        self._invoke_gui(lambda: box.movedStarted.emit(1))
        self._invoke_gui(lambda: box.show_target(1))
        self._with_rotary_critical(lambda: ctl.home(wait=True))
        try:
            actual = int(ctl.position())
        except Exception:
            actual = 0
        self._invoke_gui(box.sync_active_from_device)
        self._invoke_gui(box.clear_target)
        self._invoke_gui(lambda a=actual: box.movedFinished.emit(int(a)))

    def goto_rotary_from_program(self, target, wait=True):
        """Move the rotary valve to a target port and synchronize GUI state."""
        self.ensure_rotary_connected_from_program()
        box = self._get_rotary_box()
        ctl = box.ctl
        target = int(target)
        self._invoke_gui(lambda t=target: box.movedStarted.emit(t))
        self._invoke_gui(lambda t=target: box.show_target(t))
        self._with_rotary_critical(lambda: ctl.goto(target, wait=wait))

        if wait:
            try:
                actual = int(ctl.position())
            except Exception:
                actual = 0
            self._invoke_gui(box.sync_active_from_device)
            self._invoke_gui(box.clear_target)
            self._invoke_gui(lambda a=actual: box.movedFinished.emit(int(a)))

    def _snapshot_rotary_active(self) -> int | None:
        """
        Return the cached rotary port (1..12).
        While a move is in progress (`rotary_is_busy=True`), return `None` to mark a gap.
        Do not query the device here so plotting stays independent of hardware polling.
        """
        try:
            if self.rotary_is_busy:
                return None
            return self.rotary_last_port if (self.rotary_last_port and self.rotary_last_port > 0) else None
        except Exception:
            return None


    def _now_rel_s(self) -> float:
        """Return relative time in seconds from the sampling manager for the plot time base."""
        try:
            _, rel = sampling_manager.get_timestamps()
            return float(rel if rel is not None else 0.0)
        except Exception:
            return 0.0

    
    @QtCore.pyqtSlot(int)
    def _on_rv_active_changed(self, port: int) -> None:
        """
        Log every change of the device-reported 'Active' port with the SAME time base
        as the plot. Ignore if no measurement is running (no time base).
        """
        if sampling_manager.start_timestamp is None:
            return  # No running measurement -> skip logging.
    
        t = self._now_rel_s()
        p = int(port)
    
        # De-duplicate consecutive identical states (robust against double emits)
        if self.rotary_events and int(self.rotary_events[-1][1]) == p:
            return
    
        self.rotary_events.append((t, p if (p and p > 0) else 0))
        try:
            self.plot_area.set_rotary_events(self.rotary_events)
            self.plot_area.update()
        except Exception:
            pass

    
    def _on_rv_started(self, target: int) -> None:
        """Mark rotary movement so plotting and polling can show a movement gap."""
        self.rotary_is_busy = True
        if sampling_manager.start_timestamp is None:
            return
        t = self._now_rel_s()
        # De-duplicate: only push gap if last state was not already gap(0).
        if not self.rotary_events or int(self.rotary_events[-1][1]) != 0:
            self.rotary_events.append((t, 0))
            try:
                self.plot_area.set_rotary_events(self.rotary_events)
                self.plot_area.update()
            except Exception:
                pass

    def _on_rv_finished(self, actual: int) -> None:
        # Usually activeChanged already fired with the same 'actual'.
        self.rotary_is_busy = False
        if actual > 0:
            self.rotary_last_port = int(actual)
        if actual <= 0:
            return
        t = self._now_rel_s()
        self.rotary_events.append((t, int(actual)))
        try:
            self.plot_area.set_rotary_events(self.rotary_events)
            self.plot_area.update()
        except Exception:
            pass
    def _sync_valve_buttons(self) -> None:
        """Mirror the actual valve states back onto the GUI buttons, including automation changes."""
        mapping = getattr(self, "_valve_btn_by_valve", None)
        if not mapping:
            return
        for v in self.valves:
            btn = mapping.get(v)
            if not btn:
                continue
            state = bool(v.get_state())
            if btn.isChecked() != state:
                btn.blockSignals(True)      # Prevent recursive toggle handling through the clicked signal.
                btn.setChecked(state)       # Trigger the :checked stylesheet state and recolor the button.
                btn.blockSignals(False)

    def update_data(self):
        """
        Update plots and sensor labels after one shared acquisition tick.
        - `self.time_data` stores relative time in seconds for plotting.
        - `self.abs_time_data` stores absolute epoch timestamps for CSV export.
        """
        sample = self.measurement_sampler.sample(
            target_pressure=self.target_pressure,
            offset=self.offset,
            rotary_active=self._snapshot_rotary_active(),
        )
        if sample is None:
            return

        if SENSOR_NAME_INTERNAL in self.sensor_labels:
            self.sensor_labels[SENSOR_NAME_INTERNAL].setText(
                f"{SENSOR_NAME_INTERNAL}: {sample.measured_pressure:.1f} {UNIT_PRESSURE_MBAR}"
            )

        # Keep valve buttons synchronized with the states captured by the sampler.
        self._sync_valve_buttons()

        for label_key, value in sample.flow_values:
            if label_key in self.sensor_labels:
                self.sensor_labels[label_key].setText(f"{label_key}: {value:.1f} {UNIT_FLOW_UL_MIN}")

        for label_key, value in sample.fluigent_values:
            if label_key in self.sensor_labels:
                self.sensor_labels[label_key].setText(f"{label_key}: {value:.1f} {UNIT_PRESSURE_MBAR}")

        self.label_display.setText(
            f"Measured: {sample.measured_pressure:.1f} | "
            f"Corrected: {sample.corrected_pressure:.1f} mbar | Offset: {self.offset:.1f} mbar"
        )

        try:
            if hasattr(self, "plot_area"):
                self.plot_area.update_plot()
        except Exception as e:
            print(f"[Plot] Skipped update due to error: {e}")

    def do_csv_export(self, path=None, silent=False):
        """
        Run the CSV export.
        - If `path` is provided, perform a non-interactive export.
        - If `path` is `None`, open the export dialog.
        """

        from modules.sampling_manager import sampling_manager
    
        # --- Fetch a detached export snapshot from the shared sampling manager ---
        snapshot = sampling_manager.get_export_snapshot()
    
        # --- Collect profile-specific metadata for the CSV header ---
        try:
            valve_names = [m["editor_name"] for m in self._valve_meta]  # Editor-visible valve names in GUI order.
            valve_coils = [m["coil"] for m in self._valve_meta]          # Coil addresses in the same order as valve_names.
        except Exception:
            valve_names, valve_coils = None, None
    
        try:
            profile_name = self.hw_profile.get("name")
        except Exception:
            profile_name = None

        snapshot.with_metadata(
            offset=self.offset,
            valve_names=valve_names,
            profile_name=profile_name,
            valve_coils=valve_coils,
        )
    
        # --- Interactive GUI export ---
        if path is None:
            dlg = ExportDialog(self, snapshot=snapshot)
            dlg.exec_()
    
        # --- Non-interactive export used by automation ---
        else:
            dlg = ExportDialog(parent=self, snapshot=snapshot, silent=silent)
            dlg.save_csv(path=path, silent=silent)


    def export_csv(self):
        """Open the manual CSV export dialog."""
        self.do_csv_export(path=None, silent=False)

    def open_sampling_dialog(self):
        dlg = SamplingDialog(self)
        dlg.exec_()

        
    def open_editor(self):
        """
        Open the embedded program editor with the current device catalog.
        """
        from editor_main_embedded import EmbeddedEditorWindow
    
        device_info = self.device_catalog.to_embedded_editor_info()
    
        self.editor_window = EmbeddedEditorWindow(device_info)
        self.editor_window.show()
        
    def open_program_dialog_and_run(self):
        """
        Open a file dialog and run the selected program from the manual button.
        """
        path, _ = QFileDialog.getOpenFileName(self, "Load Program", "", "JSON Files (*.json)")
        if not path:
            return
        self.run_program_from_path(path)

    def run_program_from_path(self, path):
        """
        Run a program from a validated file path, for example from a favorite slot.
        """
        if self._program_thread_is_running():
            QMessageBox.warning(self, "Program Running", "Please stop the current program before loading a new one.")
            return

        if not isinstance(path, str) or not os.path.isfile(path):
            QMessageBox.warning(self, "File Not Found", f"The selected file does not exist:\n{path}")
            return
    
        success = self.program_runner.load_program(path)
        if not success:
            return
    
        self.set_favorites_enabled(False)
    
        self.program_thread = QThread()
        self.program_worker = ProgramWorker(self.program_runner)
        self.program_worker.moveToThread(self.program_thread)


        self.program_worker.log_message.connect(self.append_log)
        self.program_worker.finished.connect(self.program_thread.quit)
        self.program_worker.finished.connect(self.program_worker.deleteLater)
        self.program_thread.finished.connect(self.program_thread.deleteLater)
        self.program_thread.finished.connect(self._clear_program_thread_refs)
        self.program_worker.finished.connect(self.on_program_finished)
        self.program_worker.error.connect(self.handle_program_error)
        self.program_worker.stopped.connect(self.append_log)

        self.program_thread.started.connect(self.program_worker.run)
        self.btn_stop_program.setEnabled(True)
        self.btn_run_program.setEnabled(False)
        self.btn_open_editor.setEnabled(False)

        self.program_thread.start()




    def _program_thread_is_running(self):
        """Return True while a program worker thread is still active."""
        thread = getattr(self, "program_thread", None)
        try:
            return bool(thread is not None and thread.isRunning())
        except RuntimeError:
            return False


    def _clear_program_thread_refs(self):
        """Drop stale Qt object references after the worker thread has finished."""
        self.program_thread = None
        self.program_worker = None


    def select_favorite(self, index):
        """
        Select a program file for one favorite slot and show only its basename in the label.
        """
        path, _ = QFileDialog.getOpenFileName(self, "Select Program File", "", "JSON Files (*.json)")
        if path:
            self.program_favorites[index] = path
            name = os.path.basename(path)  # Display only the file name in the label.
            self.favorite_labels[index].setText(name)
            self.favorite_labels[index].setStyleSheet("color: black;")


    def run_favorite(self, index):
        path = self.program_favorites[index]
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "File not found", "The selected file does not exist.")
            self.program_favorites[index] = None
            self.favorite_labels[index].setText("No file selected")
            self.favorite_labels[index].setStyleSheet("color: gray;")
            return
    
        self.run_program_from_path(path)


    def set_favorites_enabled(self, enabled):
        for i in range(5):
            self.favorite_labels[i].setVisible(enabled)
            self.favorite_select_buttons[i].setVisible(enabled)
            self.favorite_run_buttons[i].setVisible(enabled)




    def handle_program_error(self, msg):
        log_error(f"Program error: {msg}", display_ui=True, parent=self)


    def stop_program(self):
        """
        Manually stop the currently running program.
        """
        if getattr(self, "program_worker", None) is not None:
            self.program_worker.stop()
        elif hasattr(self, "program_runner"):
            self.program_runner.stop()
        self.btn_stop_program.setEnabled(False)
            
    def toggle_log_display(self):
        self.log_visible = not self.log_visible
        self.log_display.setVisible(self.log_visible)
        self.btn_toggle_log.setText("Show Log" if not self.log_visible else "Hide Log")


    def on_program_finished(self):
        """
        Reset the program controls after normal completion or manual cancellation.
        """
        self.btn_stop_program.setEnabled(False)
        self.btn_run_program.setEnabled(True)
        self.btn_open_editor.setEnabled(True)
        self.set_favorites_enabled(True)

    def append_log(self, text):
        """
        Append one line to the on-screen log widget and the in-memory log cache.
        """
        self.log_lines.append(text)
        self.log_display.append(text)
        
    def closeEvent(self, event):
        """Confirm shutdown, then stop runtime components and reset hardware state safely."""
        reply = QMessageBox.question(
            self, "Close Application", 
            "Do you really want to close the application? All valves will be closed, and pressure will be set to 0 mbar.",
            QMessageBox.Yes | QMessageBox.No
        )
    
        if reply == QMessageBox.Yes:
            try:
                if hasattr(self, "program_runner") and self.program_runner.running:
                    self.program_runner.stop_all()
                else:
                    self.reset_all_to_default()
    
                self.timer.stop()
                self.modbus.close()
    
            except Exception as e:
                print(f"[Shutdown] Error: {e}")
                
            try:
                if hasattr(self, "rotaryBox"):
                    self.rotaryBox.shutdown()
            except Exception:
                pass
            
            event.accept()
        else:
            event.ignore()


    def reset_all_to_default(self):
        """Close all valves and reset the pressure setpoint to 0 mbar."""
        self.close_all_valves()
        self.reset_pressure_hardware_zero_mbar()
        self.append_log("All valves closed, pressure set to 0 mbar.")
        
