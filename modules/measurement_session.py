"""Measurement buffer ownership for one active acquisition session."""

from collections import deque
from dataclasses import dataclass


@dataclass
class ExportSnapshot:
    """Detached measurement data and metadata for one CSV export."""

    time_data: list
    target_data: list
    corrected_data: list
    measured_data: list
    valve_states: list
    flow_data: list
    fluigent_data: list
    sampling_interval_ms: int | None
    start_timestamp: float | None
    rotary_active: list
    offset: float = 0.0
    valve_names: list | None = None
    profile_name: str | None = None
    valve_coils: list | None = None

    def with_metadata(self, offset=0.0, valve_names=None, profile_name=None, valve_coils=None):
        """Attach export metadata that lives outside the measurement buffers."""
        self.offset = float(offset or 0.0)
        self.valve_names = list(valve_names) if valve_names else None
        self.profile_name = str(profile_name) if profile_name else None
        self.valve_coils = list(valve_coils) if valve_coils else None
        return self

    def as_legacy_tuple(self):
        """Return the tuple shape used by older export callers."""
        return (
            self.time_data,
            self.target_data,
            self.corrected_data,
            self.measured_data,
            self.valve_states,
            self.flow_data,
            self.fluigent_data,
            self.sampling_interval_ms,
            self.start_timestamp,
        )


class MeasurementSession:
    """Own all live measurement buffers used by plotting and CSV export."""

    def __init__(self, flow_channel_count=4, fluigent_channel_count=0):
        self.time_data = deque()
        self.target_data = deque()
        self.corrected_data = deque()
        self.measured_data = deque()
        self.valve_states = []
        self.flow_data = [deque() for _ in range(flow_channel_count)]
        self.fluigent_pressure_data = [deque() for _ in range(fluigent_channel_count)]
        self.abs_time_data = []
        self.rotary_active = []

    def set_fluigent_channel_count(self, count):
        """Resize Fluigent buffers after sensor discovery, keeping existing values when possible."""
        count = max(0, int(count))
        current = len(self.fluigent_pressure_data)
        if count > current:
            self.fluigent_pressure_data.extend(deque() for _ in range(count - current))
        elif count < current:
            del self.fluigent_pressure_data[count:]

    def reset(self):
        """Clear all buffers for a new measurement run."""
        self.time_data.clear()
        self.target_data.clear()
        self.corrected_data.clear()
        self.measured_data.clear()
        self.valve_states.clear()
        for channel in self.flow_data:
            channel.clear()
        for channel in self.fluigent_pressure_data:
            channel.clear()
        self.abs_time_data.clear()
        self.rotary_active.clear()

    def rollback_partial_sample(self):
        """Remove the data written before a failed pressure readout."""
        if self.time_data:
            self.time_data.pop()
        if self.abs_time_data:
            self.abs_time_data.pop()
        if self.target_data:
            self.target_data.pop()

    def snapshot_for_export(self, sampling_interval_ms, start_timestamp):
        """Return detached copies of all buffers as an ExportSnapshot."""
        return ExportSnapshot(
            time_data=list(self.abs_time_data),
            target_data=list(self.target_data),
            corrected_data=list(self.corrected_data),
            measured_data=list(self.measured_data),
            valve_states=list(self.valve_states),
            flow_data=[list(channel) for channel in self.flow_data],
            fluigent_data=[list(channel) for channel in self.fluigent_pressure_data],
            sampling_interval_ms=sampling_interval_ms,
            start_timestamp=start_timestamp,
            rotary_active=list(self.rotary_active),
        )
