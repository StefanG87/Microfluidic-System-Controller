"""Rotary valve control card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtCore import QThread, QTimer, Signal, QObject
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox, QWidget

from modules.mf_common import load_last_comport, save_last_comport
from modules.rotary_valve_controller import RotaryValveController
from modules.rvm_dt import list_serial_ports
from ui_v3.fluent_compat import BodyLabel, CardWidget, PushButton, make_card_layout


class _RotaryWorker(QObject):
    """Run one blocking rotary-controller operation outside the GUI thread."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, controller: RotaryValveController, task: str, arg=None):
        super().__init__()
        self.controller = controller
        self.task = task
        self.arg = arg

    def run(self) -> None:
        """Execute the requested rotary operation."""
        try:
            if self.task == "connect":
                args = dict(self.arg or {})
                self.controller.connect(args["port"], int(args.get("positions", 12)))
                self.finished.emit("Connected")
                return
            if self.task == "home":
                self.controller.home(wait=True)
                self.finished.emit("Homed")
                return
            if self.task == "goto":
                self.controller.goto(int(self.arg), wait=True)
                self.finished.emit(f"Goto {self.arg} done")
                return
            self.finished.emit("Done")
        except Exception as exc:
            self.error.emit(str(exc))


class RotaryCard(CardWidget):
    """Compact v2-style rotary valve control using the shared controller layer."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.runtime_controller = controller
        self.rotary = RotaryValveController()
        self._thread = None
        self._worker = None
        self._busy = False
        self._active_port = 0

        layout = make_card_layout(self)
        layout.addWidget(BodyLabel("Rotary Valve"))

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        self.com = QComboBox()
        self.refresh_button = PushButton("Refresh")
        self.connect_button = PushButton("Connect")
        top_layout.addWidget(QLabel("COM:"))
        top_layout.addWidget(self.com, 1)
        top_layout.addWidget(self.refresh_button)
        top_layout.addWidget(self.connect_button)
        layout.addWidget(top)

        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        self.status = QLabel("Status: -")
        self.info = QLabel("N: -  Pos: -  Active: -")
        status_layout.addWidget(self.status, 1)
        status_layout.addWidget(self.info)
        layout.addWidget(status_row)

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)
        self.home_button = PushButton("Home")
        self.prev_button = PushButton("Prev")
        self.next_button = PushButton("Next")
        self.goto = QComboBox()
        self.goto.addItems([str(index) for index in range(1, 13)])
        self.go_button = PushButton("Go")
        for widget in (self.home_button, self.prev_button, self.next_button):
            controls_layout.addWidget(widget)
        controls_layout.addStretch(1)
        controls_layout.addWidget(QLabel("Goto:"))
        controls_layout.addWidget(self.goto)
        controls_layout.addWidget(self.go_button)
        layout.addWidget(controls)

        self.refresh_button.clicked.connect(lambda _checked=False: self.refresh_ports())
        self.connect_button.clicked.connect(lambda _checked=False: self.connect_rotary())
        self.home_button.clicked.connect(lambda _checked=False: self.home())
        self.prev_button.clicked.connect(lambda _checked=False: self.goto_relative(-1))
        self.next_button.clicked.connect(lambda _checked=False: self.goto_relative(1))
        self.go_button.clicked.connect(lambda _checked=False: self.goto_selected())

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(300)
        self.poll_timer.timeout.connect(self.poll_status)

        self.refresh_ports()
        self._set_motion_enabled(False)
        self.runtime_controller.set_rotary_adapter(self)
        QTimer.singleShot(0, self.autoconnect_saved)

    def refresh_ports(self) -> None:
        """Refresh available COM ports and preselect the saved rotary port."""
        self.com.clear()
        for port in list_serial_ports():
            self.com.addItem(port)
        saved = load_last_comport("rotary_valve")
        if saved:
            index = self.com.findText(saved)
            if index >= 0:
                self.com.setCurrentIndex(index)

    def autoconnect_saved(self) -> None:
        """Reconnect the rotary valve automatically when a saved port is present."""
        if load_last_comport("rotary_valve") and self.com.currentText().strip():
            self.connect_rotary()

    def connect_rotary(self) -> bool:
        """Connect and home the rotary valve using the selected COM port."""
        if self._busy:
            return False
        port = self.com.currentText().strip()
        if not port:
            QMessageBox.information(self, "Rotary Valve", "Please choose a COM port.")
            return False
        self._run_worker("connect", {"port": port, "positions": 12})
        return True

    def ensure_connected(self) -> bool:
        """Connect from automation paths when the UI is not connected yet."""
        if self.rotary.is_connected():
            return True
        return self.connect_rotary()

    def home(self) -> None:
        """Home the rotary valve."""
        self._run_worker("home")

    def goto_selected(self) -> None:
        """Move to the selected port."""
        self.goto_port(int(self.goto.currentText()))

    def goto_relative(self, delta: int) -> None:
        """Move one port forward or backward."""
        try:
            current = self.rotary.position()
            count = self.rotary.num_ports()
            target = ((int(current) - 1 + int(delta)) % int(count)) + 1
        except Exception:
            target = int(self.goto.currentText())
        self.goto_port(target)

    def goto_port(self, port: int, wait: bool = True) -> None:
        """Move to one rotary port."""
        self._run_worker("goto", int(port))

    def num_ports(self) -> int:
        """Return the reported number of ports."""
        return int(self.rotary.num_ports()) if self.rotary.is_connected() else 0

    def position(self) -> int:
        """Return the reported current port."""
        return int(self.rotary.position()) if self.rotary.is_connected() else 0

    def active_port(self) -> int:
        """Return the last polled active port."""
        return int(self._active_port or 0)

    def is_connected(self) -> bool:
        """Return whether the rotary controller currently has an open connection."""
        return bool(self.rotary.is_connected())

    def _set_active_port(self, port: int | None) -> None:
        """Keep the local and runtime rotary-active state in sync."""
        try:
            self._active_port = int(port or 0)
        except Exception:
            self._active_port = 0
        self.runtime_controller.set_rotary_active_port(self._active_port)

    def _publish_rotary_catalog_state(self) -> None:
        """Refresh catalog metadata after connect/disconnect without touching hardware."""
        try:
            self.runtime_controller.refresh_rotary_catalog_state()
        except Exception as exc:
            self.runtime_controller.append_log(f"[v3] Rotary catalog update failed: {exc}")

    def _run_worker(self, task: str, arg=None) -> None:
        """Start one rotary worker and update UI state."""
        if self._busy:
            return
        if task != "connect" and not self.rotary.is_connected():
            QMessageBox.information(self, "Rotary Valve", "Please connect first.")
            return
        self._busy = True
        self.status.setText("Status: Busy")
        self._set_motion_enabled(False)
        self.poll_timer.stop()

        self._thread = QThread(self)
        self._worker = _RotaryWorker(self.rotary, task, arg)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._handle_worker_finished)
        self._worker.error.connect(self._handle_worker_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker_refs)
        self._thread.start()

    def _handle_worker_finished(self, message: str) -> None:
        """Update UI after a successful rotary operation."""
        self.status.setText(f"Status: {message}")
        if self.rotary.is_connected():
            save_last_comport(self.com.currentText().strip(), device_key="rotary_valve")
            self.poll_timer.start()
            self.poll_status()
        else:
            self._set_active_port(0)
        self._publish_rotary_catalog_state()
        self.runtime_controller.append_log(f"[v3] Rotary: {message}")

    def _handle_worker_error(self, message: str) -> None:
        """Show one rotary error without crashing the GUI."""
        self.status.setText(f"Status: ERROR: {message}")
        if not self.rotary.is_connected():
            self._set_active_port(0)
            self.info.setText("N: -  Pos: -  Active: 0")
        self._publish_rotary_catalog_state()
        self.runtime_controller.append_log(f"[v3] Rotary error: {message}")

    def _clear_worker_refs(self) -> None:
        """Release worker objects and restore buttons."""
        self._busy = False
        self._thread = None
        self._worker = None
        connected = self.rotary.is_connected()
        if not connected:
            self._set_active_port(0)
        self._set_motion_enabled(connected)

    def poll_status(self) -> None:
        """Poll current rotary status and active port."""
        if self._busy or not self.rotary.is_connected():
            return
        try:
            status = self.rotary.status()
            ports = self.rotary.num_ports()
            position = self.rotary.position()
            self._set_active_port(position)
            self.status.setText(f"Status: {status}")
            self.info.setText(f"N: {ports}  Pos: {position}  Active: {self._active_port}")
            self._sync_goto_items(ports)
        except Exception as exc:
            self.status.setText(f"Status: ERROR: {exc}")
            self.poll_timer.stop()
            try:
                self.rotary.release_connection()
            except Exception:
                pass
            self._set_active_port(0)
            self.info.setText("N: -  Pos: -  Active: 0")
            self._publish_rotary_catalog_state()
            self._set_motion_enabled(False)

    def _sync_goto_items(self, ports: int) -> None:
        """Keep the goto selector aligned with the configured port count."""
        ports = max(1, int(ports or 12))
        if self.goto.count() == ports:
            return
        current = self.goto.currentText()
        self.goto.clear()
        self.goto.addItems([str(index) for index in range(1, ports + 1)])
        index = self.goto.findText(current)
        if index >= 0:
            self.goto.setCurrentIndex(index)

    def _set_motion_enabled(self, enabled: bool) -> None:
        """Enable or disable rotary motion buttons."""
        for widget in (self.home_button, self.prev_button, self.next_button, self.goto, self.go_button):
            widget.setEnabled(bool(enabled))
