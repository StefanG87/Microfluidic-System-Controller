"""Hardware-free tests for shared preference helpers."""

from __future__ import annotations

import os
import tempfile
import unittest

from modules.mf_common import load_program_favorites, save_program_favorites


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


if __name__ == "__main__":
    unittest.main()
