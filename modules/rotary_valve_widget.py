from __future__ import annotations
from typing import Optional
from PyQt5 import QtCore, QtWidgets
import sip
from modules.rvm_dt import list_serial_ports
from modules.rotary_valve_controller import RotaryValveController
from modules.mf_common import load_last_comport, save_last_comport
from modules.device_catalog import ACTUATOR_NAME_ROTARY_VALVE


class _RVWorker(QtCore.QObject):
    """
    Runs exactly one controller task off the UI thread.
    Emits 'finished' with a short message on success, or 'error' with details.
    """
    finished = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    def __init__(self, task: str, ctl: RotaryValveController, arg=None):
        super().__init__()
        self.task = task
        self.ctl = ctl
        self.arg = arg

    @QtCore.pyqtSlot()
    def run(self) -> None:
        try:
            if self.task == "connect":
                args = self.arg or {}
                self.ctl.connect(args["port"], args.get("positions", 12))
                self.finished.emit("Connected, set positions, homed.")
                return
            if self.task == "home":
                self.ctl.home(wait=True)
                self.finished.emit("Homed.")
                return
            if self.task == "goto":
                self.ctl.goto(int(self.arg), wait=True)
                self.finished.emit(f"Goto {self.arg} done.")
                return
            self.finished.emit("No-op")
        except Exception as e:
            self.error.emit(str(e))


class RotaryValveQBox(QtWidgets.QGroupBox):
    """
    Compact control for the rotary valve: Connect, Home, Prev/Next, Goto,
    and a periodic poll that updates N/Pos/Status labels.

    Design goals:
    - Plot remains responsive (no long locks on UI thread).
    - 'Active' always reflects device-reported position.
    - Goto combobox mirrors port count 1..N and selection is robustly committed.
    """

    movedStarted = QtCore.pyqtSignal(int)
    movedFinished = QtCore.pyqtSignal(int)
    activeChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(ACTUATOR_NAME_ROTARY_VALVE, parent)
        self.ctl = RotaryValveController()
        self._worker_thread: Optional[QtCore.QThread] = None
        self._worker: Optional[_RVWorker] = None

        # Internal state
        self._busy: bool = False
        self._last_active: int = 0
        self._pending_port: Optional[str] = None

        # --- UI: top row (port selection & connect) ---
        self.cmbCom = QtWidgets.QComboBox()
        self.btnRefresh = QtWidgets.QPushButton("Refresh")
        self.btnConnect = QtWidgets.QPushButton("Connect")
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("COM:"))
        top.addWidget(self.cmbCom, 14)
        top.addWidget(self.btnRefresh)
        top.addWidget(self.btnConnect)

        # --- UI: mid row (status labels) ---
        self.lblStatus = QtWidgets.QLabel("Status: -")
        self.lblN = QtWidgets.QLabel("N: -")
        self.lblPos = QtWidgets.QLabel("Pos: -")
        self.lblActive = QtWidgets.QLabel("Active: -")
        mid = QtWidgets.QHBoxLayout()
        mid.addWidget(self.lblStatus, 1)
        mid.addWidget(self.lblN)
        mid.addWidget(self.lblPos)
        mid.addWidget(self.lblActive)

        # --- UI: bottom row (controls) ---
        self.btnHome = QtWidgets.QPushButton("Home")
        self.btnPrev = QtWidgets.QPushButton("Prev")
        self.btnNext = QtWidgets.QPushButton("Next")
        self.cmbGoto = QtWidgets.QComboBox()
        self.cmbGoto.addItems([str(i) for i in range(1, 13)])  # default 12
        self.btnGoto = QtWidgets.QPushButton("Go")
        bot = QtWidgets.QHBoxLayout()
        bot.addWidget(self.btnHome)
        bot.addWidget(self.btnPrev)
        bot.addWidget(self.btnNext)
        bot.addStretch(1)
        bot.addWidget(QtWidgets.QLabel("Goto:"))
        bot.addWidget(self.cmbGoto)
        bot.addWidget(self.btnGoto)

        # Layout
        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(mid)
        lay.addLayout(bot)

        # Signals
        self.btnRefresh.clicked.connect(self._refresh)
        self.btnConnect.clicked.connect(self._connect)
        self.btnHome.clicked.connect(lambda: self._run("home"))
        self.btnPrev.clicked.connect(lambda: self._goto_relative(-1))
        self.btnNext.clicked.connect(lambda: self._goto_relative(+1))
        self.btnGoto.clicked.connect(self._goto_from_ui)  # use robust UI reader

        # Periodic polling
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self._poll)

        # Init UI
        self._set_enabled(False)
        self._refresh()
        # Auto-connect next tick if a saved COM exists
        QtCore.QTimer.singleShot(0, self._autoconnect_if_saved)

    # ------------- actions -------------

    def _refresh(self) -> None:
        """Enumerate serial ports into the COM combobox and preselect last used."""
        self.cmbCom.clear()
        for d in list_serial_ports():
            self.cmbCom.addItem(d)
        try:
            last = load_last_comport("rotary_valve")
            if last:
                idx = self.cmbCom.findText(last)
                if idx >= 0:
                    self.cmbCom.setCurrentIndex(idx)
        except Exception:
            pass

    def refresh_config_status(self) -> dict:
        """Refresh available COM ports and probe the current connection without moving the valve."""
        previous_ports = self._listed_com_ports()
        self._refresh()
        current_ports = self._listed_com_ports()

        status = {
            "ports_added": sorted(set(current_ports) - set(previous_ports)),
            "ports_removed": sorted(set(previous_ports) - set(current_ports)),
            "connected": self.ctl.is_connected(),
            "reachable": None,
            "device_status": "",
            "error": "",
        }

        if not status["connected"]:
            return status

        try:
            device_status = self.ctl.status()
            status["reachable"] = True
            status["device_status"] = device_status
            self.lblStatus.setText("Status: " + device_status)
        except Exception as e:
            status["reachable"] = False
            status["error"] = str(e)
            self.lblStatus.setText("Status: ERROR: " + str(e))

        return status

    def _autoconnect_if_saved(self) -> None:
        try:
            last = load_last_comport("rotary_valve")
            if not last:
                return
            idx = self.cmbCom.findText(last)
            if idx < 0:
                return
            self.cmbCom.setCurrentIndex(idx)
            self._connect()
        except Exception:
            pass

    def _connect(self) -> None:
        """Connect to the selected COM and start controller-side homing."""
        if self._thread_alive():
            return
        port = self.cmbCom.currentText().strip()
        if not port:
            QtWidgets.QMessageBox.information(self, "Info", "Please choose a COM port.")
            return
        self._pending_port = port
        self._run("connect", {"port": port, "positions": 12})

    # ---- GOTO entry points ----

    def _goto_from_ui(self) -> None:
        """Read target from the combobox robustly and issue a goto."""
        if self._busy or self._thread_alive():
            return
        if not self.ctl.is_connected():
            QtWidgets.QMessageBox.information(self, "Info", "Please connect first.")
            return

        # If popup is open, first commit selection; read highlighted item if needed.
        pos = self._read_goto_value()
        if not isinstance(pos, int) or pos <= 0:
            return
        self._goto_to(int(pos))

    def _goto_to(self, port: int) -> None:
        """Single path for all goto commands (used by UI and Prev/Next)."""
        if self._busy or self._thread_alive():
            return
        if not self.ctl.is_connected():
            QtWidgets.QMessageBox.information(self, "Info", "Please connect first.")
            return

        # Reflect intent in UI (without fighting user interaction).
        try:
            idx = self.cmbGoto.findText(str(int(port)))
            if idx >= 0 and not self._user_interacting_goto():
                self.cmbGoto.blockSignals(True)
                self.cmbGoto.setCurrentIndex(idx)
        except Exception:
            pass
        finally:
            try:
                self.cmbGoto.blockSignals(False)
            except Exception:
                pass

        # Visual hint + execute
        try:
            self.show_target(int(port))
        except Exception:
            pass

        self.pause_polling()
        self.movedStarted.emit(int(port))
        self._run("goto", int(port))

    def _goto_relative(self, delta: int) -> None:
        """
        Compute target = (current +/- 1) wrapped 1..N, then call _goto_to(target).
        This avoids reading the combobox (no commit races).
        """
        if self._busy or self._thread_alive():
            return
        if not self.ctl.is_connected():
            QtWidgets.QMessageBox.information(self, "Info", "Please connect first.")
            return
        try:
            n = int(self.ctl.num_ports())
            p = int(self.ctl.position())
            if not (n and p and p > 0):
                return
            target = ((p - 1 + int(delta)) % n) + 1
        except Exception:
            return
        self._goto_to(target)

    def home(self) -> None:
        """Home with proper UI/poll orchestration."""
        if self._busy or self._thread_alive():
            return
        self.pause_polling()
        self.movedStarted.emit(1)
        self._run("home")

    def _run(self, task: str, arg=None) -> None:
        """Start a single-use worker thread for a controller operation."""
        if task != "connect" and not self.ctl.is_connected():
            QtWidgets.QMessageBox.information(self, "Info", "Please connect first.")
            return
        if self._busy or self._thread_alive():
            return
        self._set_enabled(False)
        self.lblStatus.setText(f"Status: {task} ...")
        self._busy = True

        self._worker_thread = QtCore.QThread(self)
        self._worker = _RVWorker(task, self.ctl, arg)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._done)
        self._worker.error.connect(self._err)

        # Release the one-shot worker objects after the task finishes.
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._thread_cleared)

        self._worker_thread.start()

    def _done(self, msg: str) -> None:
        """
        After worker finished, read back device position once and update UI+signals.
        """
        self._busy = False
        self.lblStatus.setText("Status: " + msg)

        actual = 0
        try:
            actual = int(self.ctl.position())
        except Exception:
            actual = 0

        if actual > 0:
            self.lblActive.setText(f"Active: {actual}")
            self.lblActive.setStyleSheet("")
            if not self._user_interacting_goto():
                idx = self.cmbGoto.findText(str(actual))
                if idx >= 0:
                    try:
                        self.cmbGoto.blockSignals(True)
                        self.cmbGoto.setCurrentIndex(idx)
                    finally:
                        self.cmbGoto.blockSignals(False)
        else:
            self.lblActive.setText("Active: -")
            self.lblActive.setStyleSheet("")

        if actual != self._last_active:
            self._last_active = actual
            self.activeChanged.emit(int(actual))

        self.movedFinished.emit(int(actual))
        self._set_enabled(True)
        self.resume_polling()

        # Persist last COM on successful connect
        try:
            if self.ctl.is_connected() and self._pending_port:
                save_last_comport(self._pending_port, device_key="rotary_valve")
                self._pending_port = None
        except Exception:
            pass

    def _err(self, msg: str) -> None:
        """Handle worker errors and re-enable UI appropriately."""
        self._busy = False
        self.lblStatus.setText("Status: ERROR: " + msg)
        self.movedFinished.emit(0)
        self._set_enabled(self.ctl.is_connected())
        self.resume_polling()

    def _poll(self) -> None:
        """
        Periodic status poll: update N/Pos/Status/Active.
        Make exactly ONE position() call and reuse it for labels and combo sync.
        Emit activeChanged(...) when the active port changes.
        """
        if not self.ctl.is_connected():
            self.lblN.setText("N: -")
            self.lblPos.setText("Pos: -")
            self.lblStatus.setText("Status: -")
            self.lblActive.setText("Active: -")
            if self._last_active != 0:
                self._last_active = 0
                self.activeChanged.emit(0)
            return

        # N (and adjust combobox range 1..N)
        try:
            n = int(self.ctl.num_ports())
            self.lblN.setText(f"N: {n}")
            if n > 0 and self.cmbGoto.count() != n:
                self._rebuild_goto_items(n)
        except Exception:
            self.lblN.setText("N: -")

        # Single position read
        try:
            p = int(self.ctl.position())
            self.lblPos.setText(f"Pos: {p if p and p > 0 else '-'}")
        except Exception:
            p = None
            self.lblPos.setText("Pos: -")

        # Status string
        try:
            self.lblStatus.setText("Status: " + self.ctl.status())
        except Exception as e:
            self.lblStatus.setText("Status: ERROR: " + str(e))

        # Active + optional combo sync (only if user not interacting / not busy)
        try:
            if p and p > 0:
                self.lblActive.setText(f"Active: {p}")
            else:
                self.lblActive.setText("Active: -")

            if (not self._busy) and (not self._user_interacting_goto()) and p and p > 0:
                idx = self.cmbGoto.findText(str(p))
                if idx >= 0:
                    try:
                        self.cmbGoto.blockSignals(True)
                        self.cmbGoto.setCurrentIndex(idx)
                    finally:
                        self.cmbGoto.blockSignals(False)

            current_active = int(p or 0)
            if current_active != self._last_active:
                self._last_active = current_active
                self.activeChanged.emit(current_active)
        except Exception:
            self.lblActive.setText("Active: -")

    # ------------- UI enable/disable & threading helpers -------------

    def _set_enabled(self, connected: bool) -> None:
        self.btnConnect.setEnabled(not connected)
        self.cmbCom.setEnabled(not connected)
        self.btnRefresh.setEnabled(not connected)

        self.btnHome.setEnabled(connected)
        self.btnPrev.setEnabled(connected)
        self.btnNext.setEnabled(connected)
        self.btnGoto.setEnabled(connected)
        self.cmbGoto.setEnabled(connected)

    def _thread_alive(self) -> bool:
        t = getattr(self, "_worker_thread", None)
        return bool(t) and not sip.isdeleted(t) and t.isRunning()

    def _thread_cleared(self, *_) -> None:
        self._worker_thread = None
        self._worker = None

    # ------------- lifecycle -------------

    def shutdown(self) -> None:
        try:
            if self.timer.isActive():
                self.timer.stop()
        except Exception:
            pass
        try:
            if self._thread_alive():
                self._worker_thread.quit()
                self._worker_thread.wait(1500)
        except Exception:
            pass
        try:
            self.ctl.disconnect()
        except Exception:
            pass

    def pause_polling(self):
        try:
            if self.timer.isActive():
                self.timer.stop()
        except Exception:
            pass

    def resume_polling(self):
        try:
            if not self.timer.isActive():
                self.timer.start()
        except Exception:
            pass

    # --- public helpers for external status indication (ProgramRunner) ---

    def show_target(self, port: int):
        """Visual hint of the target port; no device state change."""
        try:
            self.lblActive.setText(f"Target: {int(port)}")
            self.lblActive.setStyleSheet("font-weight:600;")
            idx = self.cmbGoto.findText(str(int(port)))
            if idx >= 0:
                self.cmbGoto.setCurrentIndex(idx)
        except Exception:
            pass

    def sync_active_from_device(self):
        """Force-refresh 'Active' from device (also updates combo)."""
        try:
            p = self.ctl.position()
            txt = f"{p}" if p and p > 0 else "-"
            self.lblActive.setText(f"Active: {txt}")
            self.lblActive.setStyleSheet("")
            idx = self.cmbGoto.findText(str(p))
            if p and idx >= 0:
                self.cmbGoto.setCurrentIndex(idx)
        except Exception:
            self.lblActive.setText("Active: -")
            self.lblActive.setStyleSheet("")

    def clear_target(self):
        """Clear target emphasis and trigger a single poll refresh."""
        self.lblActive.setStyleSheet("")
        self._poll()

    def _user_interacting_goto(self) -> bool:
        """
        True while the user interacts with the combobox (popup open or has focus).
        Prevents poll-driven combo sync from overriding user choice.
        """
        try:
            if self.cmbGoto.hasFocus():
                return True
            view = getattr(self.cmbGoto, "view", lambda: None)()
            return bool(view and view.isVisible())
        except Exception:
            return False

    # ------------- internal helpers -------------

    def _rebuild_goto_items(self, n: int) -> None:
        """Rebuild [1..n] without emitting signals; keep previous selection if valid."""
        if n <= 0:
            return
        try:
            cur = self.cmbGoto.currentText()
            self.cmbGoto.blockSignals(True)
            self.cmbGoto.clear()
            self.cmbGoto.addItems([str(i) for i in range(1, n + 1)])
            idx = self.cmbGoto.findText(cur)
            if idx >= 0:
                self.cmbGoto.setCurrentIndex(idx)
        except Exception:
            pass
        finally:
            try:
                self.cmbGoto.blockSignals(False)
            except Exception:
                pass

    def _listed_com_ports(self) -> list[str]:
        """Return the COM ports currently shown in the widget."""
        return [self.cmbCom.itemText(i) for i in range(self.cmbCom.count())]

    def _read_goto_value(self) -> Optional[int]:
        """
        Robustly read the intended Goto port:
        - if popup is open, read the view's highlighted row and commit it
        - else, read the combobox's currentText
        """
        try:
            view = getattr(self.cmbGoto, "view", lambda: None)()
            if view is not None and view.isVisible():
                idx = view.currentIndex().row()
                if idx < 0:
                    # fallback: index under mouse cursor
                    from PyQt5 import QtGui
                    idx_obj = view.indexAt(view.viewport().mapFromGlobal(QtGui.QCursor.pos()))
                    idx = idx_obj.row()
                if idx >= 0:
                    # commit the highlighted choice and return it
                    self.cmbGoto.setCurrentIndex(idx)
                    return int(self.cmbGoto.itemText(idx))
            return int(self.cmbGoto.currentText())
        except Exception:
            return None
