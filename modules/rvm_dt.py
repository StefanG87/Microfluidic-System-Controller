# rvm_dt.py
# Clean DT-protocol client for AMF RVM rotary valves (12-port default)
# Python 3.10+, dependencies: pyserial
#
# Protocol per AMF Operating Manual:
# - Frame: "/<addr><cmd><CR>" ; reply begins with "/0..." and ends with ETX CR LF
# - Commands that MUST be executed with trailing 'R': moves (B/I/O...), init (Z/Y), some control
# - Commands that MUST NOT use 'R': queries starting with '?', configuration starting with '!', and T/X/H/Q
#   (see “Command Execution Guidelines” and the RVM command set).  [AMF manual]
# - Status polling: '?9200' → 0 = Done, 255 = Busy, 0x90 = Not homed.  [AMF manual]
#
# Robustness:
# - Uses serial.read_until('\n') with retries (pySerial docs) to tolerate delayed/partial replies.
# - Treats any reply starting with '/0' as OK (covers '/0@' and text OKs like "!8012" → "/0'12 ports mode").
# - If a move’s reply is empty, we validate acceptance by checking '?9200' (Busy/Done).
#
# Copyright: you may reuse in your lab; no warranty.

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional, Sequence

import serial
from serial.tools import list_ports


class RVMError(RuntimeError):
    """High-level error for valve communication / state issues."""


@dataclass
class RVMConfig:
    """Serial and protocol knobs. Adjust only if you know what you’re doing."""
    address: int = 1              # Device address (1..9/A..E); default is 1
    baudrate: int = 9600          # 9600 8N1 per manual
    timeout_s: float = 2.0        # read timeout
    write_timeout_s: float = 2.0  # write timeout
    settle_poll_ms: int = 50      # polling cadence for wait_until_done()


VALID_PORT_COUNTS = (4, 6, 8, 10, 12, 16, 20, 24)


def list_serial_ports() -> Sequence[str]:
    """Return OS port names (COMx on Windows, /dev/tty... on Linux/macOS)."""
    return [p.device for p in list_ports.comports()]


class RVM:
    """
    Minimal, manual-accurate DT client for AMF RVM valves.

    Key manual facts we honor:
    - Most commands require trailing 'R'; query (!) and config (?) do NOT.  [AMF manual]
    - '?'9200 gives detailed status; do not send new commands while Busy.  [AMF manual]
    - '!50<n>' sets reply mode; we use '0' (synchronous).  [AMF manual]
    - '!80<n>' sets number of ports; reply is textual, still starts with '/0'.  [AMF manual]
    """

    def __init__(self, port: str, cfg: Optional[RVMConfig] = None):
        self.port = port
        self.cfg = cfg or RVMConfig()
        self.ser: Optional[serial.Serial] = None
        self.debug = False  # set True to print raw frames


    # ---------------- Connection lifecycle ----------------

    def open(self) -> None:
        """Open the serial port and ping the device."""
        self.ser = serial.Serial(
            self.port,
            baudrate=self.cfg.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=self.cfg.timeout_s,
            write_timeout=self.cfg.write_timeout_s,
        )
        self.ping()  # sanity check

    def close(self) -> None:
        """Abort any running motion (T) and close the serial port."""
        try:
            self.abort_if_busy()
        finally:
            if self.ser:
                try:
                    self.ser.close()
                finally:
                    self.ser = None

    # ---------------- High-level commands ----------------

    def ping(self) -> None:
        """Check communications using the detailed status query."""
        ans = self._send("?9200")
        if not ans.startswith("/0"):
            raise RVMError(f"Device did not acknowledge: {ans!r}")

    def enforce_sync_answer_mode(self) -> None:
        """Force synchronous replies (answer mode 0). !50<n> has no trailing 'R'."""
        self._send("!500", expect_ok=True)  # reply starts with '/0...'

    def get_num_ports(self) -> int:
        """Return valve position count, or 0 if the firmware didn't report it."""
        v = self._extract_int(self._send("?801"), default=0)
        return v if v in VALID_PORT_COUNTS else 0

    def set_num_ports(self, n: int) -> None:
        """Set valve position count if different. !80<n> (no 'R')."""
        if n not in VALID_PORT_COUNTS:
            raise ValueError("Unsupported number of positions")
        current = self.get_num_ports()
        if current != n:
            self._send(f"!80{n}", expect_ok=True)  # textual OK is fine
            time.sleep(0.05)

    def home(self, wait: bool = True) -> None:
        """Home the valve (ZR) and optionally wait until Done."""
        self._send("ZR", expect_ok=True)
        if wait:
            self.wait_until_done()

    def goto_shortest(self, port: int, *, block: bool = True) -> None:
        """Go to absolute port using shortest path (B<n>R)."""
        if not (1 <= port <= 24):
            raise ValueError("Invalid port")
        self._send(f"B{port}R", expect_ok=True)
        if block:
            self.wait_until_done()

    def step_inc(self) -> None:
        """+1 step (wrap), direction agnostic (uses shortest path)."""
        n = self.get_num_ports() or 12
        cur = self.position() or 1
        tgt = (cur % n) + 1
        self._send(f"B{tgt}R", expect_ok=True)
        self.wait_until_done()

    def step_dec(self) -> None:
        """–1 step (wrap), direction agnostic (uses shortest path)."""
        n = self.get_num_ports() or 12
        cur = self.position() or 1
        tgt = (cur - 2) % n + 1
        self._send(f"B{tgt}R", expect_ok=True)
        self.wait_until_done()

    def position(self) -> int:
        """Return current port index (?6)."""
        return self._extract_int(self._send("?6"), default=0)

    def status_code(self) -> int:
        """Return detailed status (?9200): 0 Done, 255 Busy, 0x90 Not homed, etc."""
        return self._extract_int(self._send("?9200"), default=0xFF)

    def wait_until_done(self, timeout_s: float = 10.0) -> None:
        """Poll '?9200' until status is Done or an error/timeout occurs."""
        t_end = time.time() + timeout_s
        while time.time() < t_end:
            s = self.status_code()
            if s == 0:
                return
            if s in (0x90, 0xE0, 0xE1, 0xE2, 0xE3, 0xE4):
                raise RVMError(f"Valve error/status {hex(s)}")
            time.sleep(self.cfg.settle_poll_ms / 1000.0)
        raise TimeoutError("Timeout waiting for Done")

    def abort_if_busy(self) -> None:
        """Send T (hard stop, no 'R') if the valve is currently Busy."""
        try:
            if self.status_code() == 0xFF:
                self._send("T")  # stop current motion; no trailing 'R'
                t_end = time.time() + 2.0
                while time.time() < t_end and self.status_code() == 0xFF:
                    time.sleep(0.05)
        except Exception:
            # best-effort stop; still close the port
            pass

    # ---------------- Low-level send/parse ----------------

    def _send(self, payload: str, *, expect_ok: bool = False) -> str:
        """
        Send a DT frame and read a full reply frame.
    
        Manual: replies begin with '/0' and end with ETX (0x03) + CR + LF.
        We read until '\r' (carriage return) to be resilient on platforms that
        might deliver '\n' late or drop the first byte. Then we optionally
        drain a trailing '\n'.  (pySerial read_until docs / common pattern)
        """
        if not self.ser:
            raise RVMError("Serial not open")
    
        frame = f"/{self.cfg.address}{payload}\r"
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(frame.encode("ascii"))
    
        # --- primary read: until '\r' (CR), more robust than '\n'
        raw = self.ser.read_until(b"\r")
        ans = raw.decode("ascii", errors="ignore")
    
        # drain a single trailing '\n' if present (manual: ETX CR LF)
        if getattr(self.ser, "in_waiting", 0):
            peek = self.ser.read(1)
            if peek != b"\n":
                # push back not available → just ignore (no functional impact)
                pass
    
        # Retry on empty/short frames (device or driver may be slightly late)
        if len(ans) < 2:
            for _ in range(3):
                time.sleep(0.05)
                chunk = self.ser.read_until(b"\r")
                if chunk:
                    ans = chunk.decode("ascii", errors="ignore")
                    # optional: drain '\n' again
                    if getattr(self.ser, "in_waiting", 0):
                        _ = self.ser.read(1)
                    break
    
        # --- frame recovery: some stacks can lose the very first '/'
        # Accept if it *starts with '/0'*, or reconstruct if it *starts with '0'*
        norm = ans.strip()
        if self.debug:
            print(f"TX: {frame!r}  RX: {norm!r}")

        if norm.startswith("0"):
            norm = "/" + norm
        # Sometimes ETX is visible as '\x03' right before CR/LF → keep it
    
        if expect_ok:
            # OK if the normalized reply starts with '/0' (covers '/0@' and text OKs)
            if norm.startswith("/0"):
                return norm
            # If the device didn't echo an immediate OK for a move, validate by status
            try:
                stat = self._extract_int(self._send("?9200"), default=0xFF)
                if stat in (0xFF, 0x00, 0x90):  # Busy / Done / Not homed
                    return norm or "/0@"
            except Exception:
                pass
            raise RVMError(f"Command failed: {payload!r} \u2192 {ans!r}")
    
        return norm


    @staticmethod
    def _extract_int(ans: str, default: int = 0) -> int:
        """Pull the last integer found in a DT reply; return default if none."""
        m = re.findall(r"(\d+)", ans)
        return int(m[-1]) if m else default
