"""Hardware-free tests for shared preference helpers."""

from __future__ import annotations

import os
import tempfile
import unittest

from modules.mf_common import (
    load_export_read_timing_enabled,
    load_export_prefix,
    load_program_favorites,
    save_export_read_timing_enabled,
    save_export_prefix,
    save_program_favorites,
)


class PreferenceHelperTests(unittest.TestCase):
    """Verify that small JSON preference helpers preserve expected data."""

    def test_program_favorites_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "device_prefs.json")
            favorites = [
                r"C:\programs\prime.json",
                None,
                r"C:\programs\ramp.json",
            ]

            self.assertTrue(save_program_favorites(favorites, path=path))
            loaded = load_program_favorites(count=5, path=path)

            self.assertEqual(loaded[:3], favorites)
            self.assertEqual(loaded[3:], [None, None])

    def test_export_read_timing_roundtrip_preserves_other_preferences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "device_prefs.json")
            favorites = [r"C:\programs\prime.json"]

            self.assertTrue(save_program_favorites(favorites, path=path))
            self.assertFalse(load_export_read_timing_enabled(path=path))
            self.assertTrue(save_export_read_timing_enabled(True, path=path))

            self.assertTrue(load_export_read_timing_enabled(path=path))
            self.assertEqual(load_program_favorites(count=1, path=path), favorites)

    def test_export_prefix_roundtrip_preserves_other_preferences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "device_prefs.json")
            favorites = [r"C:\programs\prime.json"]

            self.assertTrue(save_program_favorites(favorites, path=path))
            self.assertEqual(load_export_prefix(path=path), "measurement")
            self.assertTrue(save_export_prefix("kinetics", path=path))

            self.assertEqual(load_export_prefix(path=path), "kinetics")
            self.assertEqual(load_program_favorites(count=1, path=path), favorites)


if __name__ == "__main__":
    unittest.main()
