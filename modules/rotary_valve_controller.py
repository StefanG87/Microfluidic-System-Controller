
from __future__ import annotations
import threading
from typing import Optional
import time
from modules.rvm_dt import RVM, RVMConfig, RVMError

class RotaryValveController:
    """
    High-level controller for a single AMF RVM device.
    Safe for calls from different threads via an internal lock.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._rvm: Optional[RVM] = None
        self._connected_port: Optional[str] = None
        self._desired_positions = 12  # default; can be overridden via connect()

    def is_connected(self) -> bool:
        with self._lock:
            return self._rvm is not None

    def connect(self, com_port: str, positions: int = 12) -> None:
        """
        Open serial, enforce synchronous answers, set positions, then home.
        More robust against first-try non-ack by retrying once after a short delay.
        """
        import time
        with self._lock:
            if self._rvm is not None:
                try:
                    self._rvm.close()
                except Exception:
                    pass
                self._rvm = None
    
            cfg = RVMConfig()
            rvm = RVM(com_port, cfg)
            rvm.open()
    
            # Robust initialization sequence with one retry.
            def _init_sequence():
                # enforce sync answers; tolerate devices already in mode 0
                try:
                    rvm.enforce_sync_answer_mode()   # !500
                except Exception:
                    pass
                if positions:
                    rvm.set_num_ports(positions)     # !80n
                rvm.home(wait=True)                  # ZR (+ wait Done)
    
            try:
                _init_sequence()
            except Exception:
                # Some controllers do not acknowledge immediately after open, so retry once after a short delay.
                time.sleep(0.2)
                _init_sequence()
    
            self._rvm = rvm
            self._com = com_port
            self._desired_positions = positions


    def disconnect(self) -> None:
        with self._lock:
            if self._rvm:
                try:
                    self._rvm.abort_if_busy()  # T (no 'R') if Busy
                except Exception:
                    pass
                try:
                    self._rvm.close()
                finally:
                    self._rvm = None
                    self._connected_port = None

    # -------------- motion --------------

    def _wait_until_done(self, poll_interval: float = 0.05, timeout: float | None = None) -> None:
        start = time.monotonic()
        while True:
            with self._lock:
                self._ensure()
                code = self._rvm.status_code()  # very short status request
            if code == 0x00:  # Done
                return
            if timeout is not None and (time.monotonic() - start) > timeout:
                raise RVMError("Timeout while waiting for RVM to finish.")
            time.sleep(poll_interval)

    def home(self, wait: bool = True) -> None:
        # Send the motion command while holding the lock, but do not block while waiting.
        with self._lock:
            self._ensure()
            # Many firmware APIs accept wait/block flags; force non-blocking behavior here.
            try:
                self._rvm.home(wait=False)
            except TypeError:
                # Fallback when home(wait=...) is unavailable: trigger a plain non-blocking home call.
                self._rvm.home()  # starts the move
        if wait:
            self._wait_until_done()

    def goto(self, port: int, wait: bool = True) -> None:
        with self._lock:
            self._ensure()
            try:
                n = int(self._rvm.get_num_ports()) or int(self._desired_positions)
            except Exception:
                n = int(self._desired_positions)
            if not (1 <= int(port) <= int(n)):
                raise RVMError(f"Requested port {port} is out of range 1..{n}")
    
            # Try the preferred API first.
            try:
                self._rvm.goto_shortest(int(port), block=False)
            except (TypeError, AttributeError):
                try:
                    self._rvm.goto(int(port), block=False)
                except TypeError:
                    self._rvm.goto(int(port))  # last-resort fallback
    
        if wait:
            self._wait_until_done()

    # -------------- status --------------

    def status(self) -> str:
        """
        Returns a human-friendly status string based on ?9200.
        """
        with self._lock:
            self._ensure()
            s = self._rvm.status_code()
            return {
                0x00: "Done",
                0xFF: "Busy",
                0x90: "Not homed",
                0xE0: "Blocked",
                0xE1: "Sensor error",
                0xE2: "Missing main ref",
                0xE3: "Missing ref",
                0xE4: "Bad ref polarity",
            }.get(s, f"Code {hex(s)}")

    def position(self) -> int:
        with self._lock:
            self._ensure()
            return self._rvm.position()

    def num_ports(self) -> int:
        with self._lock:
            self._ensure()
            n = self._rvm.get_num_ports()
            return n if n else self._desired_positions

    # -------------- helpers --------------

    def _ensure(self) -> None:
        if self._rvm is None:
            raise RVMError("Rotary valve not connected. Call connect() first.")
