"""Hardware-independent calibration measurement runner."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Event
from typing import Callable, Protocol

import numpy as np

from modules.balance import BalanceReader
from .models import CalibrationSession, MeasurementRecord, MeasurementSample


class PressureSource(Protocol):
    def setDesiredPressure(self, val: float) -> None: ...


class Valve(Protocol):
    address: int
    bus: object


class FlowSensor(Protocol):
    name: str

    def read_flow(self) -> float | None: ...


class PressureSensor(Protocol):
    def read_pressure(self) -> float | None: ...


@dataclass
class MeasurementPlan:
    pressures_mbar: list[float]
    repetitions: int
    duration_s: float
    warmup_cut_s: float = 0.7
    pressure_offset_mbar: float = 0.0
    stable_min_duration_s: float = 3.0
    stable_std_threshold_mbar: float = 1.0
    sample_interval_s: float = 0.1


class CalibrationRunner:
    """Executes a calibration plan against injected hardware adapters."""

    def __init__(
        self,
        pressure_source: PressureSource,
        pneumatic_valve: Valve,
        fluidic_valve: Valve,
        flow_sensor: FlowSensor,
        pressure_sensor: PressureSensor,
        session: CalibrationSession,
        balance: BalanceReader | None = None,
        wait_for_next_tube: Callable[[int, float], bool] | None = None,
        log: Callable[[str], None] = print,
    ):
        self.pressure_source = pressure_source
        self.pneumatic_valve = pneumatic_valve
        self.fluidic_valve = fluidic_valve
        self.flow_sensor = flow_sensor
        self.pressure_sensor = pressure_sensor
        self.session = session
        self.balance = balance
        self.wait_for_next_tube = wait_for_next_tube
        self.log = log
        self.stop_event = Event()

    def stop(self) -> None:
        self.stop_event.set()

    def run(self, plan: MeasurementPlan) -> CalibrationSession:
        self._set_valve(self.pneumatic_valve, True)
        try:
            for pressure_index, target in enumerate(plan.pressures_mbar):
                if self.stop_event.is_set():
                    break
                self.pressure_source.setDesiredPressure(target + plan.pressure_offset_mbar)
                self.log(f"[calibration] target pressure {target:.1f} mbar")
                self._wait_until_stable(plan)

                for repeat in range(plan.repetitions):
                    if self.stop_event.is_set():
                        break
                    record = self._measure_repeat(target, repeat + 1, plan)
                    self.session.add_record(record)

                    is_last = (
                        pressure_index == len(plan.pressures_mbar) - 1
                        and repeat == plan.repetitions - 1
                    )
                    if not is_last and self.wait_for_next_tube is not None:
                        next_pressure = target
                        next_repeat = repeat + 2
                        if repeat == plan.repetitions - 1:
                            next_pressure = plan.pressures_mbar[pressure_index + 1]
                            next_repeat = 1
                        if not self.wait_for_next_tube(next_repeat, next_pressure):
                            self.stop()
                            break
        finally:
            self._set_valve(self.fluidic_valve, False)
            self._set_valve(self.pneumatic_valve, False)
            self.pressure_source.setDesiredPressure(0)
        return self.session

    def _measure_repeat(self, target: float, repeat_index: int, plan: MeasurementPlan) -> MeasurementRecord:
        self.log(f"[calibration] repeat {repeat_index} at {target:.1f} mbar")
        mass_start = self.balance.read_mass_g() if self.balance else None
        self._set_valve(self.fluidic_valve, True)
        start_abs = time.time()
        samples = []
        try:
            while not self.stop_event.is_set() and time.time() - start_abs < plan.duration_s:
                elapsed = time.time() - start_abs
                flow = self.flow_sensor.read_flow()
                pressure = self.pressure_sensor.read_pressure()
                mass = self.balance.read_mass_g() if self.balance else None
                if flow is not None and pressure is not None:
                    samples.append(MeasurementSample(elapsed, float(flow), float(pressure), mass))
                time.sleep(plan.sample_interval_s)
        finally:
            self._set_valve(self.fluidic_valve, False)
        mass_end = self.balance.read_mass_g() if self.balance else None

        cut = float(plan.warmup_cut_s)
        cut_samples = [s for s in samples if s.t_s >= cut]
        if len(cut_samples) >= 2:
            t0 = cut_samples[0].t_s
            cut_samples = [
                MeasurementSample(s.t_s - t0, s.flow_ul_min, s.pressure_mbar, s.mass_g)
                for s in cut_samples
            ]
        return MeasurementRecord(
            target_pressure_mbar=float(target),
            repeat_index=repeat_index,
            samples=cut_samples,
            mass_start_g=mass_start,
            mass_end_g=mass_end,
            duration_s=max(0.0, plan.duration_s - cut),
        )

    def _wait_until_stable(self, plan: MeasurementPlan) -> None:
        values: list[float] = []
        start = time.time()
        while not self.stop_event.is_set():
            pressure = self.pressure_sensor.read_pressure()
            if pressure is not None:
                values.append(float(pressure))
                values = values[-100:]
            elapsed = time.time() - start
            if elapsed >= plan.stable_min_duration_s and len(values) >= 3:
                if float(np.std(values)) <= plan.stable_std_threshold_mbar:
                    return
            time.sleep(plan.sample_interval_s)

    @staticmethod
    def _set_valve(valve: Valve, state: bool) -> None:
        valve.bus.write_coil(valve.address, bool(state))
