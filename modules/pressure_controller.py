"""Pressure controller abstraction for Modbus-backed analog outputs."""


class PressureController:
    """Translate between pressure values in mbar and controller register values."""

    def __init__(self, bus, register, type=2):
        self.bus = bus
        self.register = register
        self.setPressure = 0
        controller = [
            [10, 5000.0, 10.0],
            [5, 1000.0, 10.0],
            [10, 1000.0, 10.0],
        ][type]
        self.inVolt, self.pmax, self.pmin = controller
        self.intRange = int(round(self.inVolt / 10.0 * 32767, 0))

    def setDesiredPressure(self, val):
        try:
            val = self.mbarToBit(val)
            self.bus.write_register(self.register, val)
        except Exception as e:
            print("setDesiredPressure failed:", e)

    def getRawMonitorValue(self):
        try:
            response = self.bus.read_input_registers(self.register, count=1)
            if hasattr(response, "registers") and response.registers:
                return response.registers[0]
        except Exception as e:
            print("Error reading raw value:", e)
        return None

    def mbarToBit(self, val):
        m = self.intRange / (self.pmax - self.pmin)
        n = -m * self.pmin
        return max(0, min(int(round(m * val + n, 0)), self.intRange))

    def bitToMbar(self, val):
        m = 13107 / (self.pmax - self.pmin)
        n = 16384 - m * self.pmax
        return round((val - n) / m, 1)