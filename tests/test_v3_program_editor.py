"""Model-level smoke tests for the v3 program editor window."""

import json
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from modules import program_contract as contract
from modules.program_contract import PARAM_PRESSURE, STEP_SET_PRESSURE, STEP_WAIT
from ui_v3.editor.editor_window import ProgramEditorWindow


class V3ProgramEditorTests(unittest.TestCase):
    """Verify v2-style editor list operations that do not require dialogs."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.editor = ProgramEditorWindow()
        self.editor.steps = [
            {"type": STEP_SET_PRESSURE, "params": {PARAM_PRESSURE: 25.0}, "active": True},
            {"type": STEP_WAIT, "params": {"time_sec": 1.0}, "active": True},
        ]
        self.editor._refresh_list()

    def tearDown(self):
        self.editor.close()
        self.editor.deleteLater()

    def test_duplicate_selected_steps_can_be_undone_and_redone(self):
        self.editor.list_widget.item(0).setSelected(True)
        self.editor.list_widget.item(1).setSelected(True)

        self.editor._duplicate_selected_step()

        self.assertEqual(len(self.editor.steps), 4)
        self.assertEqual(self.editor.steps[2]["type"], STEP_SET_PRESSURE)
        self.assertEqual(self.editor.steps[3]["type"], STEP_WAIT)

        self.editor._undo()

        self.assertEqual(len(self.editor.steps), 2)

        self.editor._redo()

        self.assertEqual(len(self.editor.steps), 4)

    def test_load_save_roundtrip_preserves_current_program_contract_steps(self):
        program = _representative_program()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = os.path.join(tmpdir, "source_program.json")
            target_path = os.path.join(tmpdir, "saved_program.json")
            with open(source_path, "w", encoding="utf-8") as handle:
                json.dump(program, handle, indent=2)

            self.assertTrue(self.editor.load_file(source_path))
            self.assertEqual(self.editor.steps, program)

            self.assertTrue(self.editor._write_file(target_path))
            with open(target_path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)

        self.assertEqual(saved, program)


def _representative_program():
    """Return one JSON-compatible program covering the current editor contract."""
    return [
        {"type": contract.STEP_SET_PRESSURE, "params": {contract.PARAM_PRESSURE: 50.0}, "active": True},
        {"type": contract.STEP_SET_PRESSURE_ZERO, "params": {}, "active": True},
        {"type": contract.STEP_ADD_PRESSURE, "params": {contract.PARAM_DELTA_MBAR: 5.0}, "active": True},
        {
            "type": contract.STEP_VALVE,
            "params": {contract.PARAM_VALVE_NAME: "Valve 1", contract.PARAM_STATUS: contract.STATUS_OPEN},
            "active": True,
        },
        {"type": contract.STEP_WAIT, "params": {contract.PARAM_TIME_SEC: 1.5}, "active": True},
        {
            "type": contract.STEP_WAIT_FOR_SENSOR_EVENT,
            "params": {
                contract.PARAM_SENSOR: "Internal",
                contract.PARAM_CONDITION: ">",
                contract.PARAM_TARGET_VALUE: 10.0,
                contract.PARAM_TOLERANCE: 0.5,
                contract.PARAM_STABLE_TIME: 2.0,
            },
            "active": True,
        },
        {
            "type": contract.STEP_START_MEASUREMENT,
            "params": {contract.PARAM_SAMPLING_INTERVAL_MS: 250},
            "active": True,
        },
        {"type": contract.STEP_STOP_MEASUREMENT, "params": {}, "active": True},
        {
            "type": contract.STEP_EXPORT_CSV,
            "params": {contract.PARAM_FILENAME_PREFIX: "roundtrip", contract.PARAM_FOLDER: ""},
            "active": True,
        },
        {"type": contract.STEP_ZERO_FLUIGENT, "params": {contract.PARAM_SENSORS: []}, "active": True},
        {
            "type": contract.STEP_LOOP,
            "params": {contract.PARAM_START_STEP: 1, contract.PARAM_END_STEP: 2, contract.PARAM_REPETITIONS: 3},
            "active": False,
        },
        {
            "type": contract.STEP_DOSE_VOLUME,
            "params": {
                contract.PARAM_FLOW_SENSOR: "Flow 1",
                contract.PARAM_PNEUMATIC_VALVE: "Pneumatic: 1",
                contract.PARAM_FLUIDIC_VALVE: "Fluidic: 5",
                contract.PARAM_TARGET_VOLUME: 25.0,
                contract.PARAM_INPUT_PRESSURE: 100.0,
            },
            "active": True,
        },
        {
            "type": contract.STEP_ROTARY_VALVE,
            "params": {
                contract.PARAM_ACTION: contract.ROTARY_ACTION_GOTO,
                contract.PARAM_PORT: 3,
                contract.PARAM_WAIT: True,
            },
            "active": True,
        },
        {
            "type": contract.STEP_PRESSURE_RAMP,
            "params": {
                contract.PARAM_START_PRESSURE: 0.0,
                contract.PARAM_END_PRESSURE: 100.0,
                contract.PARAM_DURATION: 5.0,
            },
            "active": True,
        },
        {
            "type": contract.STEP_POLYNOMIAL_PRESSURE,
            "params": {
                contract.PARAM_MODE: "linear",
                contract.PARAM_DURATION: 5.0,
                contract.PARAM_COEFFICIENTS: [10.0, 2.0],
                contract.PARAM_CLAMP_MIN: 0.0,
                contract.PARAM_CLAMP_MAX: 150.0,
                contract.PARAM_SLEW_LIMIT: 100.0,
                contract.PARAM_SAMPLE_INTERVAL: 0.25,
                contract.PARAM_SENSOR: "open_loop",
                contract.PARAM_FEEDBACK_GAIN: 0.0,
                contract.PARAM_MAX_CORRECTION: 0.0,
            },
            "active": True,
        },
        {
            "type": contract.STEP_FLOW_CONTROLLER,
            "params": {
                contract.PARAM_TARGET_FLOW: 50.0,
                contract.PARAM_SENSOR: "Flow 1",
                contract.PARAM_MAX_PRESSURE: 350.0,
                contract.PARAM_MIN_PRESSURE: 0.0,
                contract.PARAM_TOLERANCE_PERCENT: 5.0,
                contract.PARAM_STABLE_TIME: 2.0,
                contract.PARAM_CONTINUOUS: False,
                contract.PARAM_KP: 0.1,
                contract.PARAM_KI: 0.01,
                contract.PARAM_KD: 0.0,
            },
            "active": True,
        },
        {
            "type": contract.STEP_LOAD_SEQUENCE,
            "params": {contract.PARAM_FILENAME: "sequence.json", contract.PARAM_PATH: "sequence.json"},
            "active": True,
        },
        {
            "type": contract.STEP_CALIBRATE_WITH_FLUIGENT_SENSOR,
            "params": {contract.PARAM_SENSOR: "SN0000"},
            "active": True,
        },
    ]


if __name__ == "__main__":
    unittest.main()
