"""Sampling logic for reading runtime devices into a MeasurementSession."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MeasurementSample:
    """Values read during one acquisition tick."""

    abs_time: float
    rel_time: float
    measured_pressure: float
    corrected_pressure: float
    flow_values: list[tuple[str, float]]
    fluigent_values: list[tuple[str, float]]
    rotary_active: int | None


class MeasurementSampler:
    """Read active runtime devices and append one complete sample to the session."""

    def __init__(self, runtime_devices, measurement_session, timebase=None):
        self.runtime_devices = runtime_devices
        self.measurement_session = measurement_session
        if timebase is None:
            from modules.sampling_manager import sampling_manager

            timebase = sampling_manager
        self.timebase = timebase

    def sample(self, *, target_pressure, offset, rotary_active=None) -> MeasurementSample | None:
        """Read one acquisition tick; return None if the pressure readout failed."""
        abs_time, rel_time = self.timebase.get_timestamps()
        if abs_time is None or rel_time is None:
            self.timebase.reset_time()
            abs_time, rel_time = self.timebase.get_timestamps()

        self.measurement_session.begin_sample(abs_time, rel_time, target_pressure)

        raw_pressure = self._read_raw_pressure()
        if raw_pressure is None:
            self.measurement_session.rollback_partial_sample()
            return None

        measured_pressure = self.runtime_devices.pressure_source.bitToMbar(raw_pressure)
        corrected_pressure = measured_pressure - offset
        self.measurement_session.append_pressure_sample(corrected_pressure, measured_pressure)

        self.measurement_session.append_valve_states(self.runtime_devices.read_valve_states())

        flow_values = self._append_flow_values()
        fluigent_values = self._append_fluigent_values()

        self.measurement_session.append_rotary_active(rotary_active)

        return MeasurementSample(
            abs_time=abs_time,
            rel_time=rel_time,
            measured_pressure=measured_pressure,
            corrected_pressure=corrected_pressure,
            flow_values=flow_values,
            fluigent_values=fluigent_values,
            rotary_active=rotary_active,
        )

    def _read_raw_pressure(self):
        """Read the internal pressure monitor without applying offset correction."""
        pressure_source = self.runtime_devices.pressure_source
        if pressure_source is None:
            return None
        return pressure_source.getRawMonitorValue()

    def _append_flow_values(self) -> list[tuple[str, float]]:
        """Read configured flow channels and append display-safe values."""
        values = []
        for index, sensor in enumerate(self.runtime_devices.flow_sensors):
            raw_value = sensor.read_flow()
            value = raw_value if raw_value is not None else 0.0
            self.measurement_session.append_flow_value(index, value)
            values.append((getattr(sensor, "name", f"Flow {index + 1}"), value))
        return values

    def _append_fluigent_values(self) -> list[tuple[str, float]]:
        """Read detected Fluigent channels and append display-safe values."""
        values = []
        for index, sensor in enumerate(self.runtime_devices.fluigent_sensors):
            raw_value = sensor.read_pressure()
            value = raw_value if raw_value is not None else 0.0
            self.measurement_session.append_fluigent_pressure_value(index, value)
            device_sn = getattr(sensor, "device_sn", "")
            label = f"SN{device_sn}" if device_sn else f"Fluigent {index + 1}"
            values.append((label, value))
        return values
