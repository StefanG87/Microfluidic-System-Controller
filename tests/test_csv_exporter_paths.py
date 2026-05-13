"""Tests for CSV export path helpers."""

import os
import tempfile
import unittest

from modules.csv_exporter import CSVExporter


class CSVExporterPathTests(unittest.TestCase):
    """Verify stable CSV naming behavior shared by the v3 export buttons."""

    def test_normalize_csv_path_appends_missing_suffix(self):
        path = os.path.join("folder", "measurement")

        self.assertEqual(CSVExporter.normalize_csv_path(path), os.path.join("folder", "measurement.csv"))

    def test_normalize_csv_path_keeps_existing_csv_suffix(self):
        path = os.path.join("folder", "measurement.CSV")

        self.assertEqual(CSVExporter.normalize_csv_path(path), path)

    def test_generate_filename_sanitizes_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = CSVExporter.generate_filename(prefix="test run: 01", folder=tmpdir)

        self.assertTrue(os.path.basename(path).startswith("test_run_01_"))
        self.assertTrue(path.endswith(".csv"))


if __name__ == "__main__":
    unittest.main()
