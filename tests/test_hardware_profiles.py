"""Hardware-free validation for lookup hardware profiles."""

from __future__ import annotations

import unittest

from modules.device_catalog import valve_meta_from_profile_item
from modules.mf_common import list_hw_profiles, load_hardware_profile


class HardwareProfileTests(unittest.TestCase):
    """Verify that profile JSON files remain usable by GUI, editor, plot, and CSV code."""

    def test_lookup_profiles_are_listed(self):
        profiles = list_hw_profiles()

        self.assertIn("stand1", profiles)
        self.assertIn("stand2", profiles)
        self.assertNotIn("extended_pneumatic_setup", profiles)

    def test_all_lookup_profiles_have_unique_valve_names_and_coils(self):
        for profile_name in list_hw_profiles():
            with self.subTest(profile=profile_name):
                profile = load_hardware_profile(profile_name)
                items = self._profile_items(profile)

                self.assertTrue(items, f"{profile_name} does not define any valves.")
                editor_names = [str(item.get("editor_name", "")).strip() for item in items]
                coils = [int(item.get("coil")) for item in items]

                self.assertNotIn("", editor_names)
                self.assertEqual(len(editor_names), len(set(editor_names)))
                self.assertEqual(len(coils), len(set(coils)))

    def test_valve_metadata_contains_ui_and_runtime_fields(self):
        profile = load_hardware_profile("stand1")
        group = profile["valve_groups"][0]
        item = group["items"][0]

        meta = valve_meta_from_profile_item(group, item)

        self.assertEqual(meta["group"], "pneumatic")
        self.assertEqual(meta["editor_name"], "Pneumatic 1")
        self.assertEqual(meta["button_label"], "Outlet 1")
        self.assertEqual(meta["coil"], 0)
        self.assertEqual(meta["box"], "Pneumatic Valves")

    def test_stand1_profile_matches_measured_extended_mapping(self):
        profile = load_hardware_profile("stand1")
        items = self._profile_items(profile)

        pneumatic = [item for item in items if item.get("group") == "pneumatic"]
        fluidic = [item for item in items if item.get("group") == "fluidic"]
        pneumatic_coils = [int(item["coil"]) for item in pneumatic]

        self.assertEqual(len(pneumatic), 12)
        self.assertEqual(len(fluidic), 4)
        self.assertEqual(pneumatic_coils, [0, 1, 2, 3, 12, 13, 14, 15, 8, 9, 10, 11])

    def test_hidden_extended_profile_still_loads_for_compatibility(self):
        profile = load_hardware_profile("extended_pneumatic_setup")

        self.assertTrue(profile.get("hidden"))
        self.assertEqual(profile.get("replacement"), "stand1")
        self.assertEqual(len([item for item in self._profile_items(profile) if item.get("group") == "pneumatic"]), 12)

    @staticmethod
    def _profile_items(profile: dict) -> list[dict]:
        items = []
        for group in profile.get("valve_groups", []):
            items.extend(group.get("items", []))
        return items


if __name__ == "__main__":
    unittest.main()
