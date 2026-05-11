"""Hardware-free tests for ProgramRunner rotary-valve dispatch."""

from __future__ import annotations

import unittest

from modules.program_contract import (
    PARAM_ACTION,
    PARAM_PORT,
    PARAM_WAIT,
    ROTARY_ACTION_GOTO,
    ROTARY_ACTION_HOME,
    ROTARY_ACTION_NEXT,
    ROTARY_ACTION_PREV,
    STEP_ROTARY_VALVE,
)
from modules.program_runner import ProgramRunner


class DummyRotaryGui:
    """Minimal ProgramRunner adapter for rotary dispatch tests."""

    def __init__(self, num_ports=12, current_port=1):
        self.messages = []
        self.calls = []
        self.num_ports = int(num_ports)
        self.current_port = int(current_port)

    def append_log(self, message):
        self.messages.append(str(message))

    def home_rotary_from_program(self):
        self.calls.append(("home", None, None))
        self.current_port = 1

    def get_rotary_state_from_program(self):
        return self.num_ports, self.current_port

    def goto_rotary_from_program(self, target, wait=True):
        self.calls.append(("goto", int(target), bool(wait)))
        self.current_port = int(target)


class ProgramRunnerRotaryTests(unittest.TestCase):
    """Verify rotary JSON actions are mapped to controller calls correctly."""

    def _run_step(self, params, gui=None):
        gui = gui or DummyRotaryGui()
        runner = ProgramRunner(gui)
        runner.steps = [
            {
                "type": STEP_ROTARY_VALVE,
                "active": True,
                "params": params,
            }
        ]
        runner.run_program()
        return gui

    def test_rotary_goto_preserves_wait_flag(self):
        gui = self._run_step(
            {
                PARAM_ACTION: ROTARY_ACTION_GOTO,
                PARAM_PORT: 7,
                PARAM_WAIT: False,
            }
        )

        self.assertEqual(gui.calls, [("goto", 7, False)])

    def test_rotary_home_dispatches_home(self):
        gui = self._run_step({PARAM_ACTION: ROTARY_ACTION_HOME})

        self.assertEqual(gui.calls, [("home", None, None)])

    def test_rotary_next_wraps_from_last_port(self):
        gui = self._run_step(
            {PARAM_ACTION: ROTARY_ACTION_NEXT},
            gui=DummyRotaryGui(num_ports=12, current_port=12),
        )

        self.assertEqual(gui.calls, [("goto", 1, True)])

    def test_rotary_prev_wraps_from_first_port(self):
        gui = self._run_step(
            {PARAM_ACTION: ROTARY_ACTION_PREV},
            gui=DummyRotaryGui(num_ports=12, current_port=1),
        )

        self.assertEqual(gui.calls, [("goto", 12, True)])


if __name__ == "__main__":
    unittest.main()
