"""Program runner card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from ui_v3.editor.editor_window import ProgramEditorWindow
from ui_v3.fluent_compat import BodyLabel, CardWidget, CaptionLabel, LineEdit, PrimaryPushButton, PushButton, TextEdit, make_card_layout, stretch_row


class ProgramCard(CardWidget):
    """Load, run, stop, and inspect JSON automation programs."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.editor = None
        layout = make_card_layout(self)
        layout.addWidget(BodyLabel("Program Runner"))
        layout.addWidget(CaptionLabel("Runs JSON programs through ProgramRunner in a Qt6 worker thread."))

        self.path = LineEdit()
        self.path.setPlaceholderText("Program JSON path")
        self.browse_button = PushButton("Browse")
        self.run_button = PrimaryPushButton("Run Program")
        self.stop_button = PushButton("Stop")
        self.editor_button = PushButton("Open v3 Editor")
        self.log = TextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(180)

        self.browse_button.clicked.connect(lambda _checked=False: self._browse())
        self.run_button.clicked.connect(lambda _checked=False: self._run())
        self.stop_button.clicked.connect(lambda _checked=False: controller.stop_program())
        self.editor_button.clicked.connect(lambda _checked=False: self._open_editor())
        controller.log_message.connect(self._append_log)
        controller.program_state_changed.connect(self._apply_program_state)

        layout.addWidget(self.path)
        layout.addWidget(stretch_row(self.browse_button, self.run_button, self.stop_button, self.editor_button))
        layout.addWidget(self.log)
        self._apply_program_state(False)

    def _browse(self) -> None:
        """Choose a JSON program file."""
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open Program",
            "",
            "JSON programs (*.json);;All files (*)",
        )
        if path:
            self.path.setText(path)

    def _run(self) -> None:
        """Run the selected program through the controller."""
        path = self.path.text().strip()
        if not path:
            self.controller.append_log("[v3] Select a program file first.")
            return
        self.controller.run_program_from_path(path)

    def _open_editor(self) -> None:
        """Open the PySide6 program editor shell."""
        if self.editor is None:
            self.editor = ProgramEditorWindow(self)
        if self.path.text().strip():
            self.editor.load_file(self.path.text().strip(), show_errors=False)
        self.editor.show()
        self.editor.raise_()

    def _append_log(self, message: str) -> None:
        """Append one runtime message to the card log."""
        self.log.append(str(message))

    def _apply_program_state(self, running: bool) -> None:
        """Disable conflicting commands while a program is running."""
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
