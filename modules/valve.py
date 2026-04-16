"""Simple valve wrapper around one Modbus coil."""

from modules.mf_common import toggle_coil


class Valve:
    """Track and toggle the logical state of a single valve coil."""

    def __init__(self, bus, coil_address):
        self.bus = bus
        self.address = coil_address
        self.state = 0

    def toggle(self):
        try:
            self.state = toggle_coil(self.bus, self.address, self.state)
        except Exception as e:
            print(f"[Valve {self.address}] Toggle failed: {e}")

    def set_off(self):
        try:
            self.bus.write_coil(self.address, False)
            self.state = 0
        except Exception:
            pass

    def get_state(self):
        return self.state