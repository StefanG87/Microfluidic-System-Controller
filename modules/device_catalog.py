"""Runtime device catalog used to decouple hardware modules from editor lists."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


SENSOR_KIND_FLOW = "flow"
SENSOR_KIND_FLUIGENT_PRESSURE = "fluigent_pressure"
SENSOR_KIND_INTERNAL_PRESSURE = "internal_pressure"
SENSOR_KIND_WEIGHT = "weight"

ACTUATOR_KIND_PRESSURE_CONTROLLER = "pressure_controller"
ACTUATOR_KIND_ROTARY_VALVE = "rotary_valve"
ACTUATOR_KIND_VALVE = "valve"
ACTUATOR_KIND_SYRINGE_PUMP = "syringe_pump"

SENSOR_KIND_ORDER = (
    SENSOR_KIND_INTERNAL_PRESSURE,
    SENSOR_KIND_FLOW,
    SENSOR_KIND_FLUIGENT_PRESSURE,
    SENSOR_KIND_WEIGHT,
)
ACTUATOR_KIND_ORDER = (
    ACTUATOR_KIND_PRESSURE_CONTROLLER,
    ACTUATOR_KIND_VALVE,
    ACTUATOR_KIND_ROTARY_VALVE,
    ACTUATOR_KIND_SYRINGE_PUMP,
)


@dataclass(frozen=True)
class SensorDescriptor:
    """Editor-visible description of a sensor-like runtime device."""

    name: str
    kind: str
    unit: str = ""
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActuatorDescriptor:
    """Editor-visible description of an actuator-like runtime device."""

    name: str
    kind: str
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class DeviceCatalog:
    """Small registry for runtime devices exposed to editor and automation layers."""

    def __init__(self):
        self._sensors: list[SensorDescriptor] = []
        self._actuators: list[ActuatorDescriptor] = []

    @staticmethod
    def _kind_set(kinds: str | Iterable[str] | None) -> set[str] | None:
        if kinds is None:
            return None
        if isinstance(kinds, str):
            return {kinds}
        return {str(kind) for kind in kinds}

    @staticmethod
    def _ordered_by_kind(entries, kind_order):
        """Group known device kinds without disturbing registration order within a kind."""
        kind_rank = {kind: index for index, kind in enumerate(kind_order)}
        fallback_rank = len(kind_rank)
        return [
            entry
            for _, entry in sorted(
                enumerate(entries),
                key=lambda item: (
                    kind_rank.get(item[1].kind, fallback_rank),
                    item[0],
                ),
            )
        ]

    def clear_sensors(self, kind: str | Iterable[str] | None = None) -> None:
        """Remove sensor descriptors, optionally restricted to one or more kinds."""
        kinds = self._kind_set(kind)
        if kinds is None:
            self._sensors.clear()
            return
        self._sensors = [sensor for sensor in self._sensors if sensor.kind not in kinds]

    def clear_actuators(self, kind: str | Iterable[str] | None = None) -> None:
        """Remove actuator descriptors, optionally restricted to one or more kinds."""
        kinds = self._kind_set(kind)
        if kinds is None:
            self._actuators.clear()
            return
        self._actuators = [actuator for actuator in self._actuators if actuator.kind not in kinds]

    def register_sensor(
        self,
        name: str,
        kind: str,
        unit: str = "",
        source: str = "",
        **metadata,
    ) -> SensorDescriptor | None:
        """Register one sensor by its stable editor-visible name."""
        name = str(name).strip()
        if not name:
            return None
        descriptor = SensorDescriptor(
            name=name,
            kind=str(kind),
            unit=str(unit or ""),
            source=str(source or ""),
            metadata=dict(metadata),
        )
        self._sensors.append(descriptor)
        return descriptor

    def register_sensor_descriptor(self, descriptor: SensorDescriptor | None) -> SensorDescriptor | None:
        """Register a prebuilt sensor descriptor from a runtime adapter."""
        if descriptor is None or not str(descriptor.name).strip():
            return None
        self._sensors.append(descriptor)
        return descriptor

    def register_actuator(
        self,
        name: str,
        kind: str,
        source: str = "",
        **metadata,
    ) -> ActuatorDescriptor | None:
        """Register one actuator by its stable editor-visible name."""
        name = str(name).strip()
        if not name:
            return None
        descriptor = ActuatorDescriptor(
            name=name,
            kind=str(kind),
            source=str(source or ""),
            metadata=dict(metadata),
        )
        self._actuators.append(descriptor)
        return descriptor

    def register_actuator_descriptor(self, descriptor: ActuatorDescriptor | None) -> ActuatorDescriptor | None:
        """Register a prebuilt actuator descriptor from a runtime adapter."""
        if descriptor is None or not str(descriptor.name).strip():
            return None
        self._actuators.append(descriptor)
        return descriptor

    def sensors(self, kind: str | Iterable[str] | None = None) -> list[SensorDescriptor]:
        """Return sensor descriptors in a stable, UI-friendly order."""
        kinds = self._kind_set(kind)
        sensors = [
            sensor
            for sensor in self._sensors
            if kinds is None or sensor.kind in kinds
        ]
        return self._ordered_by_kind(sensors, SENSOR_KIND_ORDER)

    def actuators(self, kind: str | Iterable[str] | None = None) -> list[ActuatorDescriptor]:
        """Return actuator descriptors in a stable, UI-friendly order."""
        kinds = self._kind_set(kind)
        actuators = [
            actuator
            for actuator in self._actuators
            if kinds is None or actuator.kind in kinds
        ]
        return self._ordered_by_kind(actuators, ACTUATOR_KIND_ORDER)

    def sensor_names(self, kind: str | Iterable[str] | None = None) -> list[str]:
        """Return sensor names in the same order as the descriptor view."""
        return [sensor.name for sensor in self.sensors(kind)]

    def actuator_names(self, kind: str | Iterable[str] | None = None) -> list[str]:
        """Return actuator names in the same order as the descriptor view."""
        return [actuator.name for actuator in self.actuators(kind)]

    def valve_names(self) -> list[str]:
        """Return valves in the order used by the GUI and automation runner."""
        return self.actuator_names(ACTUATOR_KIND_VALVE)

    def to_embedded_editor_info(self) -> dict:
        """Return the legacy device-info shape consumed by the embedded editor."""
        valve_names = self.valve_names()
        return {
            "valves": len(valve_names),
            "valve_names": valve_names,
            "sensors": self.sensor_names(),
            "actuators": self.actuator_names(),
            "flow_sensors": self.sensor_names(SENSOR_KIND_FLOW),
            "fluigent_sensors": self.sensor_names(SENSOR_KIND_FLUIGENT_PRESSURE),
        }


def describe_internal_pressure_sensor(controller=None) -> SensorDescriptor:
    """Describe the pressure controller monitor as an editor-visible sensor."""
    return SensorDescriptor(
        name="Internal",
        kind=SENSOR_KIND_INTERNAL_PRESSURE,
        unit="mbar",
        source="pressure_controller",
        metadata={
            "register": getattr(controller, "register", None),
        },
    )


def describe_pressure_controller(controller=None) -> ActuatorDescriptor:
    """Describe the pressure controller as a runtime actuator."""
    return ActuatorDescriptor(
        name="Pressure Controller",
        kind=ACTUATOR_KIND_PRESSURE_CONTROLLER,
        source="modbus",
        metadata={
            "register": getattr(controller, "register", None),
            "pmin": getattr(controller, "pmin", None),
            "pmax": getattr(controller, "pmax", None),
        },
    )


def describe_flow_sensor(sensor, index: int) -> SensorDescriptor:
    """Describe one analog flow channel using metadata from its runtime object."""
    return SensorDescriptor(
        name=str(getattr(sensor, "name", f"Flow {index + 1}")),
        kind=SENSOR_KIND_FLOW,
        unit="uL/min",
        source="modbus",
        metadata={
            "index": index,
            "register": getattr(sensor, "register", None),
            "flow_min": getattr(sensor, "flow_min", None),
            "flow_max": getattr(sensor, "flow_max", None),
        },
    )


def describe_fluigent_sensor(sensor, index: int) -> SensorDescriptor:
    """Describe one Fluigent pressure sensor channel."""
    device_sn = str(getattr(sensor, "device_sn", ""))
    return SensorDescriptor(
        name=f"SN{device_sn}" if device_sn else f"Fluigent {index + 1}",
        kind=SENSOR_KIND_FLUIGENT_PRESSURE,
        unit="mbar",
        source="fluigent",
        metadata={
            "index": index,
            "device_sn": device_sn,
        },
    )


def describe_valve(meta: dict) -> ActuatorDescriptor:
    """Describe one profile-defined valve without leaking GUI layout details."""
    return ActuatorDescriptor(
        name=str(meta.get("editor_name", "")),
        kind=ACTUATOR_KIND_VALVE,
        source="modbus",
        metadata={
            "coil": meta.get("coil"),
            "group": meta.get("group"),
            "button_label": meta.get("button_label"),
            "box": meta.get("box"),
        },
    )


def describe_rotary_valve(widget=None) -> ActuatorDescriptor:
    """Describe the rotary valve UI/controller stack as one runtime actuator."""
    controller = getattr(widget, "ctl", None)
    return ActuatorDescriptor(
        name="Rotary Valve",
        kind=ACTUATOR_KIND_ROTARY_VALVE,
        source="serial",
        metadata={
            "connected": bool(controller.is_connected()) if controller is not None else False,
        },
    )
