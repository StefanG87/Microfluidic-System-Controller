"""Tests for balance parsing and gravimetric flow helpers."""

from __future__ import annotations

import unittest

from modules.balance import BalanceSample, flow_from_balance_samples, parse_mass_line


class BalanceParsingTests(unittest.TestCase):
    """Cover the Ohaus/PuTTY text formats used by the SOP workflow."""

    def test_parse_mass_line_accepts_ohaus_like_gram_lines(self):
        self.assertEqual(parse_mass_line("ST,GS,+12.345 g"), 12.345)
        self.assertEqual(parse_mass_line("12,500 g"), 12.5)
        self.assertEqual(parse_mass_line("   -0.010 g   "), -0.01)

    def test_parse_mass_line_ignores_non_mass_lines(self):
        self.assertIsNone(parse_mass_line("Time 12:00:00"))
        self.assertIsNone(parse_mass_line("12.3 mg"))

    def test_flow_from_balance_samples_returns_ul_per_min(self):
        samples = [
            BalanceSample(timestamp=None, elapsed_s=0.0, mass_g=0.0),
            BalanceSample(timestamp=None, elapsed_s=60.0, mass_g=1.0),
        ]

        flows = flow_from_balance_samples(samples, density_g_cm3=1.0, window=1)

        self.assertEqual(flows[0], 0.0)
        self.assertAlmostEqual(flows[1], 1000.0)


if __name__ == "__main__":
    unittest.main()
