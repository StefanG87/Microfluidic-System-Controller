"""Runtime device registry that keeps hardware objects and the device catalog in sync."""

from __future__ import annotations

from dataclasses import dataclass

from modules.device_catalog import (
    ACTUATOR_KIND_PRESSURE_CONTROLLER,
    ACTUATOR_KIND_ROTARY_VALVE,
    ACTUATOR_KIND_VALVE,
    DeviceCatalog,
    SENSOR_KIND_FLOW,
    SENSOR_KIND_FLUIGENT_PRESSURE,
    SENSOR_KIND_INTERNAL_PRESSURE,
    describe_flow_sensor,
    describe_fluigent_sensor,
    describe_internal_pressure_sensor,
    describe_pressure_controller,
    describe_rotary_valve,
    describe_valve,
)
from modules.device_refresh import (
    probe_configured_flow_inputs,
    probe_pressure_monitor,
    refresh_fluigent_sensor_list,
    refresh_rotary_config_status,
    summarize_device_config_refresh,
)


@dataclass(frozen=True)
class DeviceRefreshResult:
    """Result of one manual device-configuration refresh."""

    old_sensors: set[str]
    new_sensors: set[str]
    old_actuators: set[str]
    new_actuators: set[str]
    pressure_readable: bool
    flow_status: dict
    rotary_status: dict
    summary: str


class RuntimeDeviceRegistry:
    """Own runtime hardware references and publish them through a DeviceCatalog."""

    def __init__(self, catalog: DeviceCatalog | None = None):
        self.catalog = catalog or DeviceCatalog()
        self.pressure_source = None
        self.flow_sensors = []
        self.fluigent_sensors = []
        self.rotary_widget = None
        self.valves = []
        self.valve_meta = []

    def set_pressure_source(self, pressure_source) -> None:
        """Store the pressure controller used as actuator and internal monitor."""
        self.pressure_source = pressure_source

    def set_flow_sensors(self, flow_sensors) -> None:
        """Store the configured Modbus-backed flow sensor channels."""
        self.flow_sensors = list(flow_sensors or [])

    def set_fluigent_sensors(self, fluigent_sensors) -> None:
        """Store currently detected Fluigent pressure sensor channels."""
        self.fluigent_sensors = list(fluigent_sensors or [])

    def set_rotary_widget(self, rotary_widget) -> None:
        """Store the rotary valve widget/controller stack as one actuator endpoint."""
        self.rotary_widget = rotary_widget

    def set_valve_meta(self, valve_meta) -> None:
        """Store profile-derived valve metadata in GUI/automation order."""
        self.valve_meta = list(valve_meta or [])

    def set_valves(self, valves, valve_meta=None) -> None:
        """Store profile-derived valve objects and optional matching metadata."""
        self.valves = list(valves or [])
        if valve_meta is not None:
            self.set_valve_meta(valve_meta)

    def rebuild_catalog(self) -> None:
        """Rebuild all device descriptors from current runtime references."""
        self.catalog.clear_sensors()
        self.catalog.clear_actuators()
        self.register_pressure_controller()
        self.register_valves()
        self.register_rotary_valve()
        self.register_flow_sensors()
        self.register_fluigent_sensors()

    def register_pressure_controller(self) -> None:
        """Register the pressure controller as actuator and internal pressure sensor."""
        self.catalog.clear_sensors(SENSOR_KIND_INTERNAL_PRESSURE)
        self.catalog.clear_actuators(ACTUATOR_KIND_PRESSURE_CONTROLLER)
        if self.pressure_source is None:
            return
        self.catalog.register_sensor_descriptor(
            describe_internal_pressure_sensor(self.pressure_source)
        )
        self.catalog.register_actuator_descriptor(
            describe_pressure_controller(self.pressure_source)
        )

    def register_flow_sensors(self) -> None:
        """Register configured flow channels without probing hardware identity."""
        self.catalog.clear_sensors(SENSOR_KIND_FLOW)
        for index, sensor in enumerate(self.flow_sensors):
            self.catalog.register_sensor_descriptor(describe_flow_sensor(sensor, index))

    def register_fluigent_sensors(self) -> None:
        """Register currently detected Fluigent pressure sensor channels."""
        self.catalog.clear_sensors(SENSOR_KIND_FLUIGENT_PRESSURE)
        for index, sensor in enumerate(self.fluigent_sensors):
            self.catalog.register_sensor_descriptor(describe_fluigent_sensor(sensor, index))

    def register_rotary_valve(self) -> None:
        """Register the rotary valve stack as one runtime actuator."""
        self.catalog.clear_actuators(ACTUATOR_KIND_ROTARY_VALVE)
        if self.rotary_widget is None:
            return
        self.catalog.register_actuator_descriptor(describe_rotary_valve(self.rotary_widget))

    def register_valves(self) -> None:
        """Register profile-defined valves in the order used by GUI and automation."""
        self.catalog.clear_actuators(ACTUATOR_KIND_VALVE)
        for meta in self.valve_meta:
            self.catalog.register_actuator_descriptor(describe_valve(meta))

    def set_valve_state_by_index(self, index, state):
        """Set a valve by hardware-list index using the established coil-write path."""
        valve = self.valves[index]
        valve.bus.write_coil(valve.address, bool(state))
        valve.state = int(bool(state))
        return valve

    def set_valve_state_by_name(self, valve_name, state, available_valves=None):
        """Set a valve using an editor-visible name list aligned with hardware order."""
        valve_names = (
            list(available_valves)
            if available_valves is not None
            else self.catalog.valve_names()
        )
        if valve_name not in valve_names:
            return False
        index = valve_names.index(valve_name)
        self.set_valve_state_by_index(index, state)
        return True

    def close_all_valves(self) -> None:
        """Close every configured valve without changing pressure."""
        for index in range(len(self.valves)):
            self.set_valve_state_by_index(index, False)

    def read_valve_states(self) -> list:
        """Return current valve states in the GUI/profile order."""
        return [valve.get_state() for valve in self.valves]

    def get_flow_sensor_by_name(self, sensor_name):
        """Return the configured flow channel matching an editor-visible name."""
        for sensor in self.flow_sensors:
            if getattr(sensor, "name", None) == sensor_name:
                return sensor
        return None

    def get_fluigent_sensor_by_name(self, sensor_name):
        """Return the Fluigent sensor matching an editor-visible serial name."""
        sensor_name = str(sensor_name or "")
        for sensor in self.fluigent_sensors:
            device_sn = str(getattr(sensor, "device_sn", ""))
            if sensor_name in (f"SN{device_sn}", device_sn):
                return sensor
        return None

    def read_flow_sensor_value(self, sensor_name):
        """Read a flow sensor by its editor-visible channel name."""
        sensor = self.get_flow_sensor_by_name(sensor_name)
        if sensor is None:
            return None
        return sensor.read_flow()

    def read_fluigent_sensor_value(self, sensor_name):
        """Read a Fluigent sensor by its editor-visible serial name."""
        sensor = self.get_fluigent_sensor_by_name(sensor_name)
        if sensor is None:
            return None
        return sensor.read_pressure()

    def read_sensor_value(self, sensor_name, read_internal_pressure_mbar):
        """Read any cataloged sensor value through the appropriate runtime adapter."""
        descriptor = self.catalog.sensor_by_name(sensor_name)
        if descriptor is None:
            return None

        if descriptor.kind == SENSOR_KIND_INTERNAL_PRESSURE:
            return read_internal_pressure_mbar()

        if descriptor.kind == SENSOR_KIND_FLOW:
            return self.read_flow_sensor_value(descriptor.name)

        if descriptor.kind == SENSOR_KIND_FLUIGENT_PRESSURE:
            return self.read_fluigent_sensor_value(descriptor.name)

        return None

    def zero_fluigent_sensors_by_name(self, selected_sns=None):
        """Zero selected Fluigent sensors and return successful and failed serial names."""
        if selected_sns is None:
            selected_sns = set()
        elif isinstance(selected_sns, str):
            selected_sns = {selected_sns}
        else:
            selected_sns = {str(sensor_name) for sensor_name in selected_sns}
        zeroed = []
        failed = []
        for sensor in self.fluigent_sensors:
            device_sn = str(getattr(sensor, "device_sn", ""))
            sensor_tag = f"SN{device_sn}"
            if selected_sns and sensor_tag not in selected_sns and device_sn not in selected_sns:
                continue
            try:
                sensor.set_zero()
                zeroed.append(sensor_tag)
            except Exception as exc:
                failed.append((sensor_tag, exc))
        return zeroed, failed

    def refresh_detectable_devices(
        self,
        read_pressure_mbar,
        detect_fluigent_sensors,
    ) -> DeviceRefreshResult:
        """Refresh detectable device state while keeping hardware outputs unchanged."""
        old_sensors = set(self.catalog.sensor_names())
        old_actuators = set(self.catalog.actuator_names())

        pressure_readable = probe_pressure_monitor(read_pressure_mbar)
        flow_status = probe_configured_flow_inputs(self.flow_sensors)
        rotary_status = refresh_rotary_config_status(self.rotary_widget)
        self.fluigent_sensors = refresh_fluigent_sensor_list(
            self.fluigent_sensors,
            detect_fluigent_sensors,
        )

        self.rebuild_catalog()

        new_sensors = set(self.catalog.sensor_names())
        new_actuators = set(self.catalog.actuator_names())
        summary = summarize_device_config_refresh(
            old_sensors=old_sensors,
            new_sensors=new_sensors,
            old_actuators=old_actuators,
            new_actuators=new_actuators,
            pressure_readable=pressure_readable,
            flow_status=flow_status,
            rotary_status=rotary_status,
        )
        return DeviceRefreshResult(
            old_sensors=old_sensors,
            new_sensors=new_sensors,
            old_actuators=old_actuators,
            new_actuators=new_actuators,
            pressure_readable=pressure_readable,
            flow_status=flow_status,
            rotary_status=rotary_status,
            summary=summary,
        )
