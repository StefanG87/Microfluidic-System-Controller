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
from modules.fluigent_wrapper import detect_fluigent_sensors
from modules.program_runner import ProgramRunner
from modules.program_worker import ProgramWorker
from editor.modules.editor.task_globals import update_available_sensors, update_available_valves
from modules.rotary_valve_widget import RotaryValveQBox
from modules.mf_common import (
    log_error, log_info, load_pressure_offset, save_pressure_offset,
    load_last_modbus_ip, save_last_modbus_ip, load_hardware_profile,
    load_hw_profile_from_prefs, save_hw_profile_to_prefs, list_hw_profiles
)


def resource_path(relative_path):
    """Resolve icons and other bundled resources from the app root."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)

class PressureFlowGUI(QWidget):
    def __init__(self):
        super().__init__()
       
        self.program_thread = None
        self.program_worker = None

        self.setWindowTitle("Microfluidic System Controller")
        
        # --- Initial state ---
        self.offset = load_pressure_offset() 
        self.target_pressure = 0.0
        self.is_measuring = False
        self.start_timestamp = None
        self.sampling_rate = 250  # in ms
        sampling_manager.set_sampling_rate(self.sampling_rate)
        sampling_manager.reset_time()
        
        # make the GUI globally available for sampling_manager & dialogs
        app = QApplication.instance()
        if app is not None:
            app.main_window = self
        
    
        # --- Measurement buffers ---
        self.time_data = deque()       
        self.target_data = deque()
        self.corrected_data = deque()
        self.measured_data = deque()
        self.valve_states = []
        self.flow_data = [deque() for _ in range(4)]
        self.abs_time_data = []
    
        # --- Connect to Modbus ---
        try:
            self.modbus = self._connect_modbus_auto()
        except Exception as e:
            # Show a clear message and exit cleanly.
            QMessageBox.critical(self, "Connection Error", str(e))
            sys.exit(1)
    
        # --- Initialize runtime components ---
        self.pressure_source = PressureController(self.modbus, register=1, type=2)
        
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
        
        # --- Fluigent sensors ---
        self.fluigent_sensors = detect_fluigent_sensors()
        self.fluigent_pressure_data = [deque() for _ in self.fluigent_sensors]
        
        # --- Update the shared editor/runner catalogs ---
        # Valves: keep the order aligned with _valve_meta / self.valves.
        update_available_valves([m["editor_name"] for m in self._valve_meta])
        
        # Sensors: build and publish the flow + Fluigent list once.
        self.available_sensors = [f"Flow {i+1}" for i in range(4)]
        self.available_sensors.extend([f"SN{sensor.device_sn}" for sensor in self.fluigent_sensors])
        update_available_sensors(self.available_sensors)

        
        # --- Prepare display widgets ---
        self.sensor_labels = {}  # Live labels for sensor values.
        
        self.log_lines = []  # Optional cache for later persistence.

        # --- Rotary Valve ---
        self.rotaryBox = RotaryValveQBox(self)
        self.rotary_active = []  # per-sample: active rotary port (int 1..12) or None
        
        self.rotary_is_busy = False
        self.rotary_last_port = None
        
        # Connect rotary-widget signals
        if hasattr(self, "rotaryBox"):
            try:
                self.rotaryBox.movedStarted.connect(self._on_rotary_started)
                self.rotaryBox.movedFinished.connect(self._on_rotary_finished)
            except Exception:
                pass
            
        # --- Rotary active-time series for plot bands ---
        self._t0_monotonic = time.monotonic()   # reference for relative seconds
        self.rotary_events = deque(maxlen=20000)  # list of (t_rel_s: float, port: int|0)
        
        # connect signals
        self.rotaryBox.activeChanged.connect(self._on_rv_active_changed)
        
        # OPTIONAL: keep existing starts/finishes for gap logic, but not strictly needed now
        self.rotaryBox.movedStarted.connect(self._on_rv_started)
        self.rotaryBox.movedFinished.connect(self._on_rv_finished)

        # --- Prepare program execution ---
        self.program_runner = ProgramRunner(self)
        
        self.log_visible = True  # Set to False to start with the log hidden.
        self.favorite_widgets = []  # Row layouts for the favorite-program slots.


    
        # --- Start the periodic update timer ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(self.sampling_rate)
        
    
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
                self._valve_meta.append({
                    "group": str(item.get("group", "")).lower(),
                    "editor_name": str(item.get("editor_name", "")),
                    "button_label": str(item.get("button_label", "")) or str(item.get("editor_name", "")),
                    "coil": int(item.get("coil", 0)),
                    "box": group.get("box", "Valves"),
                })
    
        # Publish the editor-visible valve names in the same order used by the GUI.
        update_available_valves([m["editor_name"] for m in self._valve_meta])
    
        print("[ValveMap]", [(m["box"], m["button_label"], m["editor_name"], m["coil"]) for m in self._valve_meta])

    
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
        self.btn_set0.clicked.connect(lambda: self.pressure_source.setDesiredPressure(0))
        toolbar.addWidget(self.btn_set0)
        
        self.btn_export = QToolButton()
        self.btn_export.setIcon(QIcon(resource_path("icons/csv.png")))
        self.btn_export.setToolTip("Export CSV")
        self.btn_export.clicked.connect(self.export_csv)
        toolbar.addWidget(self.btn_export)
        
        self.btn_sampling = QToolButton()
        self.btn_sampling.setIcon(QIcon(resource_path("icons/sampling.png")))
        self.btn_sampling.setToolTip("Set sampling rate")
        self.btn_sampling.clicked.connect(self.open_sampling_dialog)
        toolbar.addWidget(self.btn_sampling)
        
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
    
        for i in range(4):
            label = QLabel(f"Flow {i+1}: -- uL/min")
            self.sensor_labels[f"Flow {i+1}"] = label
            self.sensor_layout.addWidget(label)
    
        for sensor in self.fluigent_sensors:
            sn = f"SN{sensor.device_sn}"
            label = QLabel(f"{sn}: -- mbar")
            self.sensor_labels[sn] = label
            self.sensor_layout.addWidget(label)
    
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
        
            btn_select = QPushButton("📂")
            btn_select.setFixedWidth(30)
            btn_select.clicked.connect(lambda _, idx=i: self.select_favorite(idx))
            self.favorite_select_buttons.append(btn_select)
            row.addWidget(btn_select)
        
            btn_run = QPushButton("▶")
            btn_run.setFixedWidth(30)
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
    
        # === Rechte Seite: Plot + Log ===
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
            self.timer.start(self.sampling_rate)
            print("[Fluigent] Update loop resumed.")
    
        QMessageBox.information(self, "Zero", f"{len(dialog.selected_sensors)} sensor(s) zeroed successfully.")

    def _persist_offset(self):
        """
        Save current self.offset to JSON and refresh any UI text that shows it.
        """
        ok = save_pressure_offset(self.offset)
        if not ok:
            QMessageBox.warning(self, "Offset", "Saving the offset failed.")

    def set_pressure(self):
        try:
            value = float(self.input_pressure.text())
            self.target_pressure = value
            self.pressure_source.setDesiredPressure(value + self.offset)
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number.")

    def set_sampling_rate_ms(self, value_ms):
        """Apply a new sampling interval and keep the timer and shared manager in sync."""
        value_ms = max(1, int(value_ms))
        self.sampling_rate = value_ms
        sampling_manager.set_sampling_rate(value_ms)
        if hasattr(self, "timer"):
            self.timer.setInterval(value_ms)
            if not self.timer.isActive():
                self.timer.start(value_ms)

    def start_measurement(self, automated=False, sampling_rate_hz=None):
        """Initialize a new measurement and reset the shared sampling-manager time base."""
        if not automated:
            reply = QMessageBox.question(
                self, "Start Measurement", "Clear existing data and start a new measurement?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
    
        self.is_measuring = True

        if sampling_rate_hz is not None:
            try:
                value_ms = max(1, int(round(1000.0 / float(sampling_rate_hz))))
                self.set_sampling_rate_ms(value_ms)
            except (TypeError, ValueError, ZeroDivisionError):
                pass
    
        # Reset the shared time base for plots and events.
        sampling_manager.reset_time()
        self.start_timestamp = sampling_manager.start_timestamp
    
        # Clear all measurement buffers for the new run.
        self.rotary_active.clear()
        self.time_data.clear()
        self.target_data.clear()
        self.corrected_data.clear()
        self.measured_data.clear()
        self.valve_states.clear()
        for d in self.flow_data:
            d.clear()
        for d in self.fluigent_pressure_data:
            d.clear()
        self.abs_time_data.clear()
        
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


    def _on_rotary_started(self, target: int):
        # The plot gap starts here while the rotary valve is moving.
        self.rotary_is_busy = True
        # Optional UI label update example:
        # if hasattr(self, "lblRotaryStatus"): self.lblRotaryStatus.setText(f"Rotary moving -> {target}")
    
    def _on_rotary_finished(self, final_pos: int):
        # The gap ends here; final_pos may still be 0 if the device state is unknown.
        self.rotary_is_busy = False
        if isinstance(final_pos, int) and final_pos > 0:
            self.rotary_last_port = final_pos
        # Optional UI label update example:
        # if hasattr(self, "lblRotaryStatus"): self.lblRotaryStatus.setText(f"Rotary active: {self.rotary_last_port or '-'}")

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
        """Optional explicit gap marker when movement begins."""
        if sampling_manager.start_timestamp is None:
            return
        t = self._now_rel_s()
        # De-duplicate: only push gap if last state wasn't already gap(0)
        if not self.rotary_events or int(self.rotary_events[-1][1]) != 0:
            self.rotary_events.append((t, 0))
            try:
                self.plot_area.set_rotary_events(self.rotary_events)
                self.plot_area.update()
            except Exception:
                pass

    
    def _on_rv_finished(self, actual: int) -> None:
        # Usually activeChanged already fired with the same 'actual'.
        # We can ignore or ensure final sample exists.
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
        Update measurement buffers, plots, and sensor labels using the shared sampling time base.
        - `self.time_data` stores relative time in seconds for plotting.
        - `self.abs_time_data` stores absolute epoch timestamps for CSV export.
        """
        # --- Fetch timestamps (absolute epoch + relative seconds since measurement start) ---
        abs_time, rel_time = sampling_manager.get_timestamps()
        if abs_time is None or rel_time is None:
            # Fallback: reset the time base and try once more.
            sampling_manager.reset_time()
            abs_time, rel_time = sampling_manager.get_timestamps()
    
        # Plotting uses relative time only (start = 0 s).
        self.time_data.append(rel_time)
    
        # Export keeps the absolute timestamps in a separate buffer.
        if not hasattr(self, "abs_time_data"):
            self.abs_time_data = []
        self.abs_time_data.append(abs_time)
    
        # --- Track the current target pressure ---
        self.target_data.append(self.target_pressure)
    
        # --- Read the internal pressure source ---
        raw = self.pressure_source.getRawMonitorValue()
        if raw is None:
            self._truncate_data()
            return
    
        measured = self.pressure_source.bitToMbar(raw)
        corrected = measured - self.offset
    
        self.corrected_data.append(corrected)
        self.measured_data.append(measured)
    
        # --- Capture valve states ---
        self.valve_states.append([v.get_state() for v in self.valves])
        self._sync_valve_buttons()
    
        # --- Read flow sensors ---
        for i, sensor in enumerate(self.flow_sensors):
            val = sensor.read_flow()
            value = val if val is not None else 0.0
            self.flow_data[i].append(value)
    
            label_key = f"Flow {i+1}"
            if label_key in self.sensor_labels:
                self.sensor_labels[label_key].setText(f"{label_key}: {value:.1f} uL/min")
        # --- Read Fluigent sensors ---
        for i, sensor in enumerate(self.fluigent_sensors):
            val = sensor.read_pressure()
            value = val if val is not None else 0.0
            self.fluigent_pressure_data[i].append(value)
    
            sn_key = f"SN{sensor.device_sn}"
            if sn_key in self.sensor_labels:
                self.sensor_labels[sn_key].setText(f"{sn_key}: {value:.1f} mbar")
    
        # --- Refresh the live display label ---
        self.label_display.setText(
            f"Measured: {measured:.1f} | Corrected: {corrected:.1f} mbar | Offset: {self.offset:.1f} mbar"
        )
    
        # Record the rotary state for the plot background bands.
        self.rotary_active.append(self._snapshot_rotary_active())
    
        # --- Refresh the plot ---
        try:
            if hasattr(self, "plot_area"):
                self.plot_area.update_plot()
        except Exception as e:
            print(f"[Plot] Skipped update due to error: {e}")



            
    def _truncate_data(self):
        """Roll back the partially appended sample if the pressure readout fails."""
        if len(self.time_data) > 0:
            self.time_data.pop()
        if hasattr(self, "abs_time_data") and len(self.abs_time_data) > 0:
            self.abs_time_data.pop()
        if len(self.target_data) > 0:
            self.target_data.pop()

    def do_csv_export(self, path=None, silent=False):
        """
        Run the CSV export.
        - If `path` is provided, perform a non-interactive export.
        - If `path` is `None`, open the export dialog.
        """
        from modules.export_dialog import ExportDialog
        from modules.sampling_manager import sampling_manager
    
        # --- Fetch the measurement buffers from the shared sampling manager ---
        (
            time_data,
            target_data,
            corrected_data,
            measured_data,
            valve_states,
            flow_data,
            fluigent_data,
            sampling_rate,
            start_timestamp
        ) = sampling_manager.get_all_data()
    
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
    
        # --- Interactive GUI export ---
        if path is None:
            dlg = ExportDialog(
                self,
                time_data,
                target_data,
                corrected_data,
                measured_data,
                valve_states,
                flow_data,
                fluigent_data,
                self.offset,
                sampling_rate,
                start_timestamp,
                rotary_active=list(self.rotary_active),
                valve_names=valve_names,
                profile_name=profile_name,
                valve_coils=valve_coils
            )
            dlg.exec_()
    
        # --- Non-interactive export used by automation ---
        else:
            dlg = ExportDialog(
                parent=self,
                time_data=time_data,
                target=target_data,
                corrected=corrected_data,
                measured=measured_data,
                valve_states=valve_states,
                flow_data=flow_data,
                fluigent_data=fluigent_data,
                offset=self.offset,
                sampling_rate=sampling_rate,
                start_timestamp=start_timestamp,
                rotary_active=list(self.rotary_active),
                auto_path=path,
                silent=silent,
                valve_names=valve_names,
                profile_name=profile_name,
                valve_coils=valve_coils
            )
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
    
        device_info = {
            "valves": len(self.valves),
            "valve_names": [m["editor_name"] for m in self._valve_meta],
            "flow_sensors": [fs.name for fs in self.flow_sensors],
            "fluigent_sensors": [f"SN{fs.device_sn}" for fs in self.fluigent_sensors]
        }
    
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

        # Keep the legacy attribute names as aliases while the rest of the GUI
        # still refers to them implicitly.
        self.thread = self.program_thread
        self.worker = self.program_worker

        self.program_worker.log_message.connect(self.append_log)
        self.program_worker.finished.connect(self.program_thread.quit)
        self.program_worker.finished.connect(self.program_worker.deleteLater)
        self.program_thread.finished.connect(self.program_thread.deleteLater)
        self.program_worker.finished.connect(self.on_program_finished)
        self.program_worker.error.connect(self.handle_program_error)

        self.program_thread.started.connect(self.program_worker.run)
        self.btn_stop_program.setEnabled(True)
        self.btn_run_program.setEnabled(False)
        self.btn_open_editor.setEnabled(False)

        self.program_thread.start()




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
        if hasattr(self, "program_runner"):
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
        for valve in self.valves:
            valve.bus.write_coil(valve.address, False)
            valve.state = 0

        self.pressure_source.setDesiredPressure(0)
        self.target_pressure = 0
        self.append_log("All valves closed, pressure set to 0 mbar.")
        
