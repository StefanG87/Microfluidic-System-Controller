"""Model-level smoke tests for the v3 program editor window."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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


if __name__ == "__main__":
    unittest.main()
