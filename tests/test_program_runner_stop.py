"""Hardware-free regression tests for program cancellation."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest

from modules.program_contract import (
    PARAM_CONDITION,
    PARAM_CONTINUOUS,
    PARAM_DURATION,
    PARAM_END_PRESSURE,
    PARAM_MAX_PRESSURE,
    PARAM_MIN_PRESSURE,
    PARAM_FLOW_SENSOR,
    PARAM_FLUIDIC_VALVE,
    PARAM_INPUT_PRESSURE,
    PARAM_PATH,
    PARAM_PNEUMATIC_VALVE,
    PARAM_SAMPLE_INTERVAL,
    PARAM_SENSOR,
    PARAM_STABLE_TIME,
    PARAM_START_PRESSURE,
    PARAM_TARGET_FLOW,
    PARAM_TARGET_VALUE,
    PARAM_TARGET_VOLUME,
    PARAM_TIME_SEC,
    PARAM_TOLERANCE,
    PARAM_TOLERANCE_PERCENT,
    STEP_DOSE_VOLUME,
    STEP_FLOW_CONTROLLER,
    STEP_LOAD_SEQUENCE,
    STEP_POLYNOMIAL_PRESSURE,
    STEP_PRESSURE_RAMP,
    STEP_WAIT,
    STEP_WAIT_FOR_SENSOR_EVENT,
)
from modules.program_runner import ProgramRunner


class DummyGui:
    """Minimal ProgramRunner adapter for non-hardware Wait-step tests."""

    def __init__(self):
        self.messages = []
        self.target_pressure = 0.0
        self.program_targets = []
        self.valve_states = []

    def append_log(self, message):
        self.messages.append(str(message))

    def set_target_pressure_mbar(self, value):
        self.target_pressure = float(value)

    def set_program_pressure_command_mbar(self, display_target_mbar, hardware_target_mbar):
        self.target_pressure = float(display_target_mbar)
        self.program_targets.append((float(display_target_mbar), float(hardware_target_mbar)))

    def get_target_pressure_mbar(self):
        return float(self.target_pressure)

    def read_flow_sensor_value(self, _sensor_name):
        return 0.0

    def read_program_sensor_value(self, _sensor_name):
        return 0.0

    def set_valve_state_by_name(self, valve_name, state, _available_valves=None):
        self.valve_states.append((str(valve_name), bool(state)))
        return True


class ProgramRunnerStopTests(unittest.TestCase):
    """Verify that stop requests interrupt abortable program steps."""

    def _run_and_stop(self, step, stop_after=0.15, timeout=1.0):
        gui = DummyGui()
        runner = ProgramRunner(gui)
        runner.steps = [step]

        start = time.monotonic()
        thread = threading.Thread(target=runner.run_program, daemon=True)
        thread.start()
        time.sleep(stop_after)
        runner.stop()
        thread.join(timeout=timeout)

        elapsed = time.monotonic() - start
        self.assertFalse(thread.is_alive(), f"{step['type']} did not stop within the timeout.")
        self.assertLess(elapsed, 1.2)
        self.assertFalse(runner.running)
        return gui

    def test_stop_interrupts_wait_step(self):
        self._run_and_stop(
            {
                "type": STEP_WAIT,
                "active": True,
                "params": {PARAM_TIME_SEC: 2.0},
            }
        )

    def test_stop_interrupts_pressure_ramp_step(self):
        gui = self._run_and_stop(
            {
                "type": STEP_PRESSURE_RAMP,
                "active": True,
                "params": {
                    PARAM_START_PRESSURE: 0.0,
                    PARAM_END_PRESSURE: 100.0,
                    PARAM_DURATION: 2.0,
                },
            }
        )
        self.assertLess(gui.target_pressure, 100.0)

    def test_stop_interrupts_polynomial_pressure_step(self):
        gui = self._run_and_stop(
            {
                "type": STEP_POLYNOMIAL_PRESSURE,
                "active": True,
                "params": {
                    PARAM_DURATION: 2.0,
                    PARAM_SAMPLE_INTERVAL: 0.05,
                    "sensor": "Open loop",
                    "mode": "linear",
                    "coefficients": [0.0, 20.0],
                },
            }
        )
        self.assertTrue(gui.program_targets)

    def test_stop_interrupts_sensor_event_wait_step(self):
        self._run_and_stop(
            {
                "type": STEP_WAIT_FOR_SENSOR_EVENT,
                "active": True,
                "params": {
                    PARAM_SENSOR: "Internal",
                    PARAM_CONDITION: ">",
                    PARAM_TARGET_VALUE: 999.0,
                    PARAM_TOLERANCE: 0.0,
                    PARAM_STABLE_TIME: 0.5,
                },
            }
        )

    def test_stop_interrupts_continuous_flow_controller_step(self):
        self._run_and_stop(
            {
                "type": STEP_FLOW_CONTROLLER,
                "active": True,
                "params": {
                    PARAM_SENSOR: "Flow 1",
                    PARAM_TARGET_FLOW: 100.0,
                    PARAM_MAX_PRESSURE: 100.0,
                    PARAM_MIN_PRESSURE: 0.0,
                    PARAM_TOLERANCE_PERCENT: 10.0,
                    PARAM_STABLE_TIME: 2.0,
                    PARAM_CONTINUOUS: True,
                },
            },
            timeout=1.2,
        )

    def test_stop_interrupts_dose_volume_step(self):
        gui = self._run_and_stop(
            {
                "type": STEP_DOSE_VOLUME,
                "active": True,
                "params": {
                    PARAM_FLOW_SENSOR: "Flow 1",
                    PARAM_PNEUMATIC_VALVE: "Pneumatic 1",
                    PARAM_FLUIDIC_VALVE: "Fluidic 5",
                    PARAM_TARGET_VOLUME: 9999.0,
                    PARAM_INPUT_PRESSURE: 25.0,
                },
            },
            timeout=1.2,
        )
        self.assertIn(("Fluidic 5", False), gui.valve_states)

    def test_stop_interrupts_loaded_sequence_wait_step(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sequence_path = os.path.join(tmpdir, "sequence.json")
            with open(sequence_path, "w", encoding="utf-8") as handle:
                json.dump(
                    [
                        {
                            "type": STEP_WAIT,
                            "active": True,
                            "params": {PARAM_TIME_SEC: 2.0},
                        }
                    ],
                    handle,
                )

            self._run_and_stop(
                {
                    "type": STEP_LOAD_SEQUENCE,
                    "active": True,
                    "params": {PARAM_PATH: sequence_path},
                }
            )


if __name__ == "__main__":
    unittest.main()
