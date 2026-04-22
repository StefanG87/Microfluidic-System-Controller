"""Runtime device catalog used to decouple hardware modules from editor lists."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


SENSOR_KIND_FLOW = "flow"
SENSOR_KIND_FLUIGENT_PRESSURE = "fluigent_pressure"
SENSOR_KIND_WEIGHT = "weight"

ACTUATOR_KIND_VALVE = "valve"
ACTUATOR_KIND_SYRINGE_PUMP = "syringe_pump"


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

    def sensor_names(self, kind: str | Iterable[str] | None = None) -> list[str]:
        """Return sensor names in registration order."""
        kinds = self._kind_set(kind)
        return [
            sensor.name
            for sensor in self._sensors
            if kinds is None or sensor.kind in kinds
        ]

    def actuator_names(self, kind: str | Iterable[str] | None = None) -> list[str]:
        """Return actuator names in registration order."""
        kinds = self._kind_set(kind)
        return [
            actuator.name
            for actuator in self._actuators
            if kinds is None or actuator.kind in kinds
        ]

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
            "flow_sensors": self.sensor_names(SENSOR_KIND_FLOW),
            "fluigent_sensors": self.sensor_names(SENSOR_KIND_FLUIGENT_PRESSURE),
        }
