"""Hardware-free tests for the high-level rotary valve controller."""

from __future__ import annotations

import unittest

from modules.rotary_valve_controller import RotaryValveController
from modules.rvm_dt import RVMError


class FakeRVM:
    """Small fake for exercising RotaryValveController without a serial port."""

    def __init__(self, statuses=None, ports=12):
        self.statuses = list(statuses or [0x00])
        self.ports = int(ports)
        self.status_reads = 0
        self.home_calls = []
        self.goto_calls = []

    def status_code(self):
        self.status_reads += 1
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0]

    def home(self, wait=False):
        self.home_calls.append(bool(wait))

    def get_num_ports(self):
        return self.ports

    def goto_shortest(self, port, block=False):
        self.goto_calls.append((int(port), bool(block)))


class RotaryValveControllerTests(unittest.TestCase):
    """Validate controller-level wait behavior without touching hardware."""

    def _controller_with_fake(self, fake: FakeRVM) -> RotaryValveController:
        controller = RotaryValveController()
        controller._rvm = fake
        controller._desired_positions = fake.ports
        return controller

    def test_wait_until_done_returns_after_busy_status(self):
        fake = FakeRVM(statuses=[0xFF, 0x00])
        controller = self._controller_with_fake(fake)

        controller._wait_until_done(poll_interval=0.001, timeout=0.1)

        self.assertGreaterEqual(fake.status_reads, 2)

    def test_wait_until_done_raises_on_timeout(self):
        fake = FakeRVM(statuses=[0xFF])
        controller = self._controller_with_fake(fake)

        with self.assertRaises(RVMError):
            controller._wait_until_done(poll_interval=0.001, timeout=0.005)

    def test_home_wait_false_does_not_poll_status(self):
        fake = FakeRVM(statuses=[0xFF])
        controller = self._controller_with_fake(fake)

        controller.home(wait=False)

        self.assertEqual(fake.home_calls, [False])
        self.assertEqual(fake.status_reads, 0)

    def test_goto_wait_false_does_not_poll_status(self):
        fake = FakeRVM(statuses=[0xFF])
        controller = self._controller_with_fake(fake)

        controller.goto(3, wait=False)

        self.assertEqual(fake.goto_calls, [(3, False)])
        self.assertEqual(fake.status_reads, 0)

    def test_goto_wait_true_polls_until_done(self):
        fake = FakeRVM(statuses=[0xFF, 0x00])
        controller = self._controller_with_fake(fake)

        controller.goto(4, wait=True)

        self.assertEqual(fake.goto_calls, [(4, False)])
        self.assertGreaterEqual(fake.status_reads, 2)

    def test_goto_rejects_out_of_range_ports(self):
        fake = FakeRVM(ports=12)
        controller = self._controller_with_fake(fake)

        with self.assertRaises(RVMError):
            controller.goto(13, wait=False)


if __name__ == "__main__":
    unittest.main()
