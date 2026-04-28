"""Minimal PySide6 JSON editor for v3 automation programs."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from modules.program_contract import SPECIAL_STEP_NAMES, STANDARD_STEP_NAMES
from ui_v3.fluent_compat import BodyLabel, CaptionLabel, LineEdit, PrimaryPushButton, PushButton, TextEdit, make_card_layout


class ProgramEditorWindow(QWidget):
    """Simple JSON-compatible editor that does not import PyQt5 editor widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Program Editor v3")
        self.resize(980, 640)
        self.path = None
        self.steps = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addWidget(BodyLabel("Program Editor v3"))
        root.addWidget(CaptionLabel("Early Qt6 editor shell. It preserves the JSON contract used by ProgramRunner."))

        self.file_path = LineEdit()
        self.file_path.setPlaceholderText("Program JSON path")
        root.addWidget(self.file_path)

        file_row = QHBoxLayout()
        self.open_button = PushButton("Open")
        self.save_button = PrimaryPushButton("Save")
        self.save_as_button = PushButton("Save As")
        self.validate_button = PushButton("Validate")
        for button in (self.open_button, self.save_button, self.save_as_button, self.validate_button):
            file_row.addWidget(button)
        file_row.addStretch(1)
        root.addLayout(file_row)

        splitter = QSplitter(Qt.Horizontal)
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._load_selected_step)
        splitter.addWidget(self.list_widget)

        editor = QWidget()
        editor_layout = make_card_layout(editor)
        self.active = QCheckBox("Active")
        self.active.setChecked(True)
        self.step_type = QComboBox()
        self.step_type.addItems(list(STANDARD_STEP_NAMES) + list(SPECIAL_STEP_NAMES))
        self.params = TextEdit()
        self.params.setPlaceholderText('{\n  "pressure": 50\n}')
        editor_layout.addWidget(BodyLabel("Step"))
        editor_layout.addWidget(self.active)
        editor_layout.addWidget(self.step_type)
        editor_layout.addWidget(CaptionLabel("Parameters as JSON object"))
        editor_layout.addWidget(self.params, 1)

        step_row = QHBoxLayout()
        self.add_button = PushButton("Add")
        self.update_button = PrimaryPushButton("Update")
        self.remove_button = PushButton("Remove")
        self.up_button = PushButton("Move Up")
        self.down_button = PushButton("Move Down")
        for button in (self.add_button, self.update_button, self.remove_button, self.up_button, self.down_button):
            step_row.addWidget(button)
        step_row.addStretch(1)
        editor_layout.addLayout(step_row)
        splitter.addWidget(editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        self.open_button.clicked.connect(lambda _checked=False: self._open_dialog())
        self.save_button.clicked.connect(lambda _checked=False: self.save())
        self.save_as_button.clicked.connect(lambda _checked=False: self._save_as_dialog())
        self.validate_button.clicked.connect(lambda _checked=False: self._validate_dialog())
        self.add_button.clicked.connect(lambda _checked=False: self._add_step())
        self.update_button.clicked.connect(lambda _checked=False: self._update_step())
        self.remove_button.clicked.connect(lambda _checked=False: self._remove_step())
        self.up_button.clicked.connect(lambda _checked=False: self._move_step(-1))
        self.down_button.clicked.connect(lambda _checked=False: self._move_step(1))

    def load_file(self, path: str, show_errors: bool = True) -> bool:
        """Load a program file if it is a valid JSON step list."""
        try:
            with open(path, "r", encoding="utf-8") as handle:
                steps = json.load(handle)
            self._validate_steps(steps)
        except Exception as exc:
            if show_errors:
                QMessageBox.warning(self, "Load failed", str(exc))
            return False
        self.path = str(path)
        self.file_path.setText(self.path)
        self.steps = steps
        self._refresh_list()
        return True

    def save(self) -> bool:
        """Save to the current path, asking for one if needed."""
        typed_path = self.file_path.text().strip()
        if typed_path and typed_path != self.path:
            self.path = typed_path
        if not self.path:
            return self._save_as_dialog()
        return self._write_file(self.path)

    def _open_dialog(self) -> None:
        """Open a program through a file dialog."""
        path, _filter = QFileDialog.getOpenFileName(self, "Open Program", "", "JSON programs (*.json);;All files (*)")
        if path:
            self.load_file(path)

    def _save_as_dialog(self) -> bool:
        """Save the current program under a chosen path."""
        path, _filter = QFileDialog.getSaveFileName(self, "Save Program", "", "JSON programs (*.json);;All files (*)")
        if not path:
            return False
        if Path(path).suffix.lower() != ".json":
            path = f"{path}.json"
        return self._write_file(path)

    def _write_file(self, path: str) -> bool:
        """Write the current step list as UTF-8 JSON."""
        try:
            self._validate_steps(self.steps)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(self.steps, handle, indent=2)
                handle.write("\n")
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return False
        self.path = str(path)
        self.file_path.setText(self.path)
        return True

    def _validate_dialog(self) -> None:
        """Show validation result for the current editor contents."""
        try:
            self._validate_steps(self.steps)
        except Exception as exc:
            QMessageBox.warning(self, "Validation failed", str(exc))
            return
        QMessageBox.information(self, "Validation", "Program JSON is valid.")

    def _validate_steps(self, steps) -> None:
        """Validate the top-level ProgramRunner JSON contract."""
        if not isinstance(steps, list):
            raise ValueError("Program must be a list of step objects.")
        known_types = set(STANDARD_STEP_NAMES) | set(SPECIAL_STEP_NAMES)
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ValueError(f"Step {index} must be an object.")
            if step.get("type") not in known_types:
                raise ValueError(f"Step {index} has unknown type: {step.get('type')!r}")
            if not isinstance(step.get("params", {}), dict):
                raise ValueError(f"Step {index} params must be an object.")

    def _refresh_list(self) -> None:
        """Refresh the left step list from the current model."""
        current = self.list_widget.currentRow()
        self.list_widget.clear()
        for index, step in enumerate(self.steps, start=1):
            marker = "" if step.get("active", True) else " [inactive]"
            self.list_widget.addItem(f"{index}. {step.get('type', '<missing>')}{marker}")
        if self.steps:
            self.list_widget.setCurrentRow(min(max(current, 0), len(self.steps) - 1))

    def _load_selected_step(self, row: int) -> None:
        """Load the selected step into the editor controls."""
        if row < 0 or row >= len(self.steps):
            return
        step = self.steps[row]
        step_type = step.get("type", STANDARD_STEP_NAMES[0])
        self.step_type.setCurrentText(step_type)
        self.active.setChecked(bool(step.get("active", True)))
        self.params.setPlainText(json.dumps(step.get("params", {}), indent=2))

    def _read_editor_step(self) -> dict:
        """Read one step from the right-side editor controls."""
        try:
            params = json.loads(self.params.toPlainText() or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid parameter JSON: {exc}") from exc
        if not isinstance(params, dict):
            raise ValueError("Parameters must be a JSON object.")
        return {
            "type": self.step_type.currentText(),
            "params": params,
            "active": self.active.isChecked(),
        }

    def _add_step(self) -> None:
        """Append a step from the editor controls."""
        try:
            self.steps.append(self._read_editor_step())
        except Exception as exc:
            QMessageBox.warning(self, "Add failed", str(exc))
            return
        self._refresh_list()
        self.list_widget.setCurrentRow(len(self.steps) - 1)

    def _update_step(self) -> None:
        """Replace the selected step with the editor contents."""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.steps):
            return
        try:
            self.steps[row] = self._read_editor_step()
        except Exception as exc:
            QMessageBox.warning(self, "Update failed", str(exc))
            return
        self._refresh_list()
        self.list_widget.setCurrentRow(row)

    def _remove_step(self) -> None:
        """Remove the selected step."""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.steps):
            return
        del self.steps[row]
        self._refresh_list()

    def _move_step(self, direction: int) -> None:
        """Move the selected step up or down by one slot."""
        row = self.list_widget.currentRow()
        new_row = row + direction
        if row < 0 or new_row < 0 or new_row >= len(self.steps):
            return
        self.steps[row], self.steps[new_row] = self.steps[new_row], self.steps[row]
        self._refresh_list()
        self.list_widget.setCurrentRow(new_row)
