"""Program runner card for the v3 GUI."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QWidget

from modules.mf_common import load_program_favorites, save_program_favorites
from ui_v3.editor.editor_window import ProgramEditorWindow
from ui_v3.fluent_compat import BodyLabel, CardWidget, LineEdit, PrimaryPushButton, PushButton, TextEdit, add_info_header, make_card_layout, stretch_row


class ProgramCard(CardWidget):
    """Load, run, stop, and inspect JSON automation programs."""

    def __init__(self, controller, parent=None, compact: bool = False, show_log: bool = True):
        super().__init__(parent)
        self.controller = controller
        self.compact = bool(compact)
        self.show_log = bool(show_log)
        self.editor = None
        self.favorite_count = 3 if self.compact else 5
        self.selected_path = ""
        self.favorite_paths = load_program_favorites(max(5, self.favorite_count))[: self.favorite_count]
        self.favorite_labels = []
        self.favorite_select_buttons = []
        self.favorite_run_buttons = []
        layout = make_card_layout(self)
        add_info_header(
            layout,
            "Program Control" if self.compact else "Program Runner",
            "Loads and runs JSON automation programs through ProgramRunner. "
            "Favorites store frequently used program files, and Stop requests cancellation without silently resetting hardware.",
        )

        self.path = LineEdit()
        self.path.setPlaceholderText("Program JSON path")
        if self.compact:
            self.path.setPlaceholderText("No program selected")
            self.path.setReadOnly(True)
        self.browse_button = PushButton("Browse")
        self.run_button = PrimaryPushButton("Run Program")
        self.stop_button = PushButton("Stop")
        self.editor_button = PushButton("Open Editor")
        self.log = None
        if self.show_log:
            self.log = TextEdit()
            self.log.setReadOnly(True)
            self.log.setMinimumHeight(180)

        self.browse_button.clicked.connect(lambda _checked=False: self._browse())
        self.run_button.clicked.connect(lambda _checked=False: self._run())
        self.stop_button.clicked.connect(lambda _checked=False: controller.stop_program())
        self.editor_button.clicked.connect(lambda _checked=False: self._open_editor())
        if self.log is not None:
            controller.log_message.connect(self._append_log)
        controller.program_state_changed.connect(self._apply_program_state)

        if self.favorite_count and not self.compact:
            layout.addWidget(BodyLabel("Favorites"))
        for index in range(self.favorite_count):
            layout.addWidget(self._favorite_row(index))
        self._apply_favorite_labels()

        if not self.compact:
            layout.addWidget(self.path)
        layout.addWidget(stretch_row(self.browse_button, self.run_button, self.stop_button, self.editor_button))
        if self.log is not None:
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
            self.selected_path = path if self.compact else ""
            self.path.setText(self._display_path(path) if self.compact else path)

    def _run(self) -> None:
        """Run the selected program through the controller."""
        path = self.selected_path if self.compact else self.path.text().strip()
        if not path:
            self.controller.append_log("[v3] Select a program file first.")
            return
        self.controller.run_program_from_path(path)

    def _favorite_row(self, index: int) -> QWidget:
        """Create one in-memory favorite slot like the classic GUI."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(f"Favorite {index + 1}: no file")
        label.setStyleSheet("color: #60717d;")
        select_button = PushButton("...")
        run_button = PushButton("Run")
        select_button.setFixedWidth(48)
        run_button.setFixedWidth(64)

        select_button.clicked.connect(lambda _checked=False, slot=index: self._select_favorite(slot))
        run_button.clicked.connect(lambda _checked=False, slot=index: self._run_favorite(slot))

        self.favorite_labels.append(label)
        self.favorite_select_buttons.append(select_button)
        self.favorite_run_buttons.append(run_button)

        layout.addWidget(label, 1)
        layout.addWidget(select_button)
        layout.addWidget(run_button)
        return row

    def _select_favorite(self, index: int) -> None:
        """Choose a JSON program file for a favorite slot."""
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Select Program File",
            "",
            "JSON programs (*.json);;All files (*)",
        )
        if not path:
            return
        self.favorite_paths[index] = path
        self.favorite_labels[index].setText(self._display_path(path))
        self.favorite_labels[index].setStyleSheet("color: #18202b;")
        self._save_favorites()

    def _run_favorite(self, index: int) -> None:
        """Run one favorite slot after validating that the file still exists."""
        path = self.favorite_paths[index]
        if not path or not os.path.isfile(path):
            self.favorite_paths[index] = None
            self.favorite_labels[index].setText(f"Favorite {index + 1}: no file")
            self.favorite_labels[index].setStyleSheet("color: #60717d;")
            self._save_favorites()
            self.controller.append_log("[v3] Favorite program file not found.")
            return
        self.selected_path = path if self.compact else ""
        self.path.setText(self._display_path(path) if self.compact else path)
        self.controller.run_program_from_path(path)

    def _open_editor(self) -> None:
        """Open the PySide6 program editor shell."""
        if self.editor is None:
            self.editor = ProgramEditorWindow(None)
        path = self.selected_path if self.compact else self.path.text().strip()
        if path:
            self.editor.load_file(path, show_errors=False)
        self.editor.show()
        self.editor.raise_()

    def _append_log(self, message: str) -> None:
        """Append one runtime message to the card log."""
        if self.log is not None:
            self.log.append(str(message))

    def _apply_program_state(self, running: bool) -> None:
        """Disable conflicting commands while a program is running."""
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.browse_button.setEnabled(not running)
        self.editor_button.setEnabled(not running)
        self.path.setEnabled(not running)
        for button in self.favorite_select_buttons:
            button.setEnabled(not running)
        for button in self.favorite_run_buttons:
            button.setEnabled(not running)

    @staticmethod
    def _display_path(path: str) -> str:
        """Show only the JSON file name in compact controls."""
        return os.path.basename(path) if path else ""

    def _apply_favorite_labels(self) -> None:
        """Show saved favorites as short JSON file names."""
        for index, path in enumerate(self.favorite_paths):
            if index >= len(self.favorite_labels):
                continue
            if path:
                self.favorite_labels[index].setText(self._display_path(path))
                self.favorite_labels[index].setStyleSheet("color: #18202b;")
            else:
                self.favorite_labels[index].setText(f"Favorite {index + 1}: no file")
                self.favorite_labels[index].setStyleSheet("color: #60717d;")

    def _save_favorites(self) -> None:
        """Persist this card's favorite slots while preserving slots it does not display."""
        favorites = load_program_favorites(5)
        for index, path in enumerate(self.favorite_paths):
            if index < len(favorites):
                favorites[index] = path
        save_program_favorites(favorites)
