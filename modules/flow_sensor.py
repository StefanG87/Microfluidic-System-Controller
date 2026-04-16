"""Analog flow sensor abstraction backed by Modbus input registers."""

from pymodbus.client import ModbusTcpClient


class SensirionFlowSensor:
    """Convert a 0-10 V Modbus signal into a calibrated flow value."""

    def __init__(self, bus: ModbusTcpClient, register: int, name="FlowSensor", v_min=0.0, v_max=10.0, flow_min=0.0, flow_max=1000.0):
        self.bus = bus
        self.register = register
        self.name = name
        self.v_min = v_min
        self.v_max = v_max
        self.flow_min = flow_min
        self.flow_max = flow_max

    def read_flow(self):
        """Return the current flow in uL/min, or `None` if the read fails."""
        try:
            response = self.bus.read_input_registers(self.register, count=1)
            if hasattr(response, "registers") and response.registers:
                raw = response.registers[0]
                voltage = raw * 10.0 / 32767.0
                flow = ((voltage - self.v_min) / (self.v_max - self.v_min)) * (self.flow_max - self.flow_min) + self.flow_min
                return round(flow, 2)
        except Exception as e:
            print(f"[FlowSensor {self.name}] Read failed: {e}")
        return None