"""Hardware-free tests for optional CSV read-timing metadata."""

from __future__ import annotations

import csv
import os
import tempfile
import unittest

from modules.csv_exporter import CSVExporter


class CSVExporterTimingTests(unittest.TestCase):
    """Verify that detailed timing columns remain optional and analyzable."""

    def test_read_timing_columns_are_written_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "timing.csv")

            CSVExporter.write_measurement_csv(
                path,
                time_data=[1000.0, 1000.25],
                target=[10.0, 10.0],
                corrected=[9.5, 9.6],
                measured=[11.0, 11.1],
                valve_states=[[0, 1], [1, 1]],
                flow_data=[[1.2, 1.3]],
                fluigent_data=[],
                sampling_interval_ms=250,
                start_timestamp=1000.0,
                rotary_active=[None, None],
                valve_names=["Pneumatic 1", "Pneumatic 2"],
                include_read_timing=True,
                sample_finished_time_data=[1000.012, 1000.266],
                configured_interval_data=[250, 250],
                read_timing_data=[
                    [
                        {"channel": "internal_pressure", "started_abs": 1000.001, "finished_abs": 1000.003},
                        {"channel": "flow:Flow 1", "started_abs": 1000.004, "finished_abs": 1000.006},
                    ],
                    [
                        {"channel": "internal_pressure", "started_abs": 1000.251, "finished_abs": 1000.253},
                        {"channel": "flow:Flow 1", "started_abs": 1000.254, "finished_abs": 1000.256},
                    ],
                ],
            )

            with open(path, newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.reader(handle, delimiter=";"))

            header_index = next(index for index, row in enumerate(rows) if row and row[0] == "Absolute Time [ISO]")
            header = rows[header_index]
            data = rows[header_index + 1]
            second_data = rows[header_index + 2]

            self.assertIn("Sample Duration [ms]", header)
            self.assertIn("Configured Interval [ms]", header)
            self.assertIn("Actual Sample Period [ms]", header)
            self.assertIn("internal_pressure read start offset [ms]", header)
            self.assertIn("flow:Flow 1 read duration [ms]", header)
            self.assertEqual(data[header.index("Configured Interval [ms]")], "250")
            self.assertEqual(data[header.index("Actual Sample Period [ms]")], "")
            self.assertEqual(second_data[header.index("Actual Sample Period [ms]")], "250,000")
            self.assertEqual(data[header.index("Sample Duration [ms]")], "12,000")
            self.assertEqual(data[header.index("internal_pressure read duration [ms]")], "2,000")

    def test_read_timing_columns_are_omitted_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "compact.csv")

            CSVExporter.write_measurement_csv(
                path,
                time_data=[1000.0],
                target=[10.0],
                corrected=[9.5],
                measured=[11.0],
                valve_states=[],
                flow_data=[],
                fluigent_data=[],
                sampling_interval_ms=250,
                start_timestamp=1000.0,
            )

            with open(path, newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.reader(handle, delimiter=";"))

            header = rows[next(index for index, row in enumerate(rows) if row and row[0] == "Absolute Time [ISO]")]

            self.assertNotIn("Sample Duration [ms]", header)
            self.assertFalse(any(row and row[0] == "Detailed read timing" for row in rows))


if __name__ == "__main__":
    unittest.main()
