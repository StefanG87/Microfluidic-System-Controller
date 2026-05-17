"""PySide6 program editor for v3 automation programs."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from modules.program_contract import SPECIAL_STEP_NAMES, STANDARD_STEP_NAMES
from ui_v3.editor.task_dialogs import edit_step_params, format_step_summary
from ui_v3.fluent_compat import BodyLabel, CaptionLabel, LineEdit, PrimaryPushButton, PushButton, TextEdit, make_card_layout, mark_primary_action


class ProgramEditorWindow(QWidget):
    """JSON-compatible editor that uses v3-native task parameter dialogs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowTitle("Program Editor")
        self.resize(980, 640)
        self.path = None
        self.steps = []
        self.undo_stack = []
        self.redo_stack = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addWidget(BodyLabel("Program Editor"))

        self.file_path = LineEdit()
        self.file_path.setPlaceholderText("Program JSON path")

        file_row = QHBoxLayout()
        file_row.addWidget(self.file_path, 1)
        self.new_button = PushButton("New")
        self.open_button = PushButton("Open")
        self.save_button = mark_primary_action(PrimaryPushButton("Save"))
        self.save_as_button = PushButton("Save As")
        self.validate_button = PushButton("Validate")
        self.undo_button = PushButton("Undo")
        self.redo_button = PushButton("Redo")
        for button in (
            self.new_button,
            self.open_button,
            self.save_button,
            self.save_as_button,
            self.validate_button,
            self.undo_button,
            self.redo_button,
        ):
            file_row.addWidget(button)
        root.addLayout(file_row)

        splitter = QSplitter(Qt.Horizontal)

        palette = QWidget()
        palette_layout = QVBoxLayout(palette)
        palette_layout.setContentsMargins(0, 0, 0, 0)
        palette_layout.setSpacing(6)
        palette_layout.addWidget(BodyLabel("Tasks"))
        for task_name in STANDARD_STEP_NAMES:
            button = PushButton(task_name)
            button.clicked.connect(lambda _checked=False, name=task_name: self._add_task_by_name(name))
            palette_layout.addWidget(button)
        palette_layout.addWidget(BodyLabel("Special Tasks"))
        for task_name in SPECIAL_STEP_NAMES:
            button = PushButton(task_name)
            button.clicked.connect(lambda _checked=False, name=task_name: self._add_task_by_name(name))
            palette_layout.addWidget(button)
        palette_layout.addStretch(1)

        palette_scroll = QScrollArea()
        palette_scroll.setWidgetResizable(True)
        palette_scroll.setWidget(palette)
        splitter.addWidget(palette_scroll)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(BodyLabel("Program Steps"))
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.currentRowChanged.connect(self._load_selected_step)
        self.list_widget.itemSelectionChanged.connect(self._apply_selection_state)
        right_layout.addWidget(self.list_widget, 2)

        step_row = QHBoxLayout()
        self.duplicate_button = PushButton("Duplicate Selected")
        self.edit_params_button = PushButton("Edit Parameters")
        self.update_button = mark_primary_action(PrimaryPushButton("Update"))
        self.remove_button = PushButton("Delete Selected")
        self.up_button = PushButton("Move Up")
        self.down_button = PushButton("Move Down")
        for button in (
            self.duplicate_button,
            self.edit_params_button,
            self.update_button,
            self.remove_button,
            self.up_button,
            self.down_button,
        ):
            step_row.addWidget(button)
        step_row.addStretch(1)
        right_layout.addLayout(step_row)

        editor = QWidget()
        editor_layout = make_card_layout(editor)
        self.active = QCheckBox("Active")
        self.active.setChecked(True)
        self.step_type = QComboBox()
        self.step_type.addItems(list(STANDARD_STEP_NAMES) + list(SPECIAL_STEP_NAMES))
        self.params = TextEdit()
        self.params.setPlaceholderText('{\n  "pressure": 50\n}')
        editor_layout.addWidget(BodyLabel("Selected Step"))
        editor_layout.addWidget(self.active)
        editor_layout.addWidget(self.step_type)
        editor_layout.addWidget(CaptionLabel("Parameters as JSON object"))
        editor_layout.addWidget(self.params, 1)

        right_layout.addWidget(editor, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 1)

        self.new_button.clicked.connect(lambda _checked=False: self._new_program())
        self.open_button.clicked.connect(lambda _checked=False: self._open_dialog())
        self.save_button.clicked.connect(lambda _checked=False: self.save())
        self.save_as_button.clicked.connect(lambda _checked=False: self._save_as_dialog())
        self.validate_button.clicked.connect(lambda _checked=False: self._validate_dialog())
        self.undo_button.clicked.connect(lambda _checked=False: self._undo())
        self.redo_button.clicked.connect(lambda _checked=False: self._redo())
        self.duplicate_button.clicked.connect(lambda _checked=False: self._duplicate_selected_step())
        self.edit_params_button.clicked.connect(lambda _checked=False: self._edit_selected_params())
        self.update_button.clicked.connect(lambda _checked=False: self._update_step())
        self.remove_button.clicked.connect(lambda _checked=False: self._remove_step())
        self.up_button.clicked.connect(lambda _checked=False: self._move_step(-1))
        self.down_button.clicked.connect(lambda _checked=False: self._move_step(1))
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._edit_selected_params())
        self._apply_history_state()
        self._apply_selection_state()

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
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._refresh_list()
        self._apply_history_state()
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
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open Program",
            self._dialog_start_folder(),
            "JSON programs (*.json);;All files (*)",
        )
        if path:
            self.load_file(path)

    def _save_as_dialog(self) -> bool:
        """Save the current program under a chosen path."""
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save Program",
            self._dialog_start_folder(),
            "JSON programs (*.json);;All files (*)",
        )
        if not path:
            return False
        if Path(path).suffix.lower() != ".json":
            path = f"{path}.json"
        return self._write_file(path)

    def _new_program(self) -> None:
        """Clear the editor and start a new in-memory program."""
        if self.steps:
            answer = QMessageBox.question(
                self,
                "New Program",
                "Clear the current program in the editor?\n\nSave first if you need to keep these changes.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            self._save_state()
        self.steps = []
        self.path = None
        self.file_path.clear()
        self._refresh_list()
        self._apply_selection_state()

    def _dialog_start_folder(self) -> str:
        """Return the current program folder for open/save dialogs."""
        if self.path:
            return str(Path(self.path).parent)
        typed_path = self.file_path.text().strip()
        if typed_path:
            return str(Path(typed_path).parent)
        return ""

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
            self.list_widget.addItem(f"{index}. {format_step_summary(step)}{marker}")
        if self.steps:
            self.list_widget.setCurrentRow(min(max(current, 0), len(self.steps) - 1))
        self._apply_selection_state()

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

    def _add_task_by_name(self, task_name: str) -> None:
        """Append a new task from the left task palette after editing its parameters."""
        params = edit_step_params(self, str(task_name), {}, step_count=len(self.steps) + 1)
        if params is None:
            return
        self._save_state()
        self.steps.append({
            "type": str(task_name),
            "params": params,
            "active": True,
        })
        self._refresh_list()
        self.list_widget.setCurrentRow(len(self.steps) - 1)

    def _add_step(self) -> None:
        """Append a step from the editor controls."""
        try:
            step = self._read_editor_step()
        except Exception as exc:
            QMessageBox.warning(self, "Add failed", str(exc))
            return
        self._save_state()
        self.steps.append(step)
        self._refresh_list()
        self.list_widget.setCurrentRow(len(self.steps) - 1)

    def _duplicate_selected_step(self) -> None:
        """Duplicate selected steps directly below the selected block."""
        rows = self._selected_rows()
        if not rows:
            return
        self._save_state()
        copies = [deepcopy(self.steps[row]) for row in rows if 0 <= row < len(self.steps)]
        insert_at = rows[-1] + 1
        for offset, step in enumerate(copies):
            self.steps.insert(insert_at + offset, step)
        self._refresh_list()
        self._select_rows(range(insert_at, insert_at + len(copies)))

    def _edit_selected_params(self) -> None:
        """Open the task-specific parameter dialog for the selected step."""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.steps):
            return

        try:
            edited_step = self._read_editor_step()
        except Exception as exc:
            QMessageBox.warning(self, "Edit failed", str(exc))
            return

        params = edit_step_params(
            self,
            edited_step["type"],
            edited_step.get("params", {}),
            step_count=len(self.steps),
        )
        if params is None:
            return

        self._save_state()
        edited_step["params"] = params
        self.steps[row] = edited_step
        self._refresh_list()
        self.list_widget.setCurrentRow(row)
        self._load_selected_step(row)

    def _update_step(self) -> None:
        """Replace the selected step with the editor contents."""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.steps):
            return
        try:
            step = self._read_editor_step()
        except Exception as exc:
            QMessageBox.warning(self, "Update failed", str(exc))
            return
        self._save_state()
        self.steps[row] = step
        self._refresh_list()
        self.list_widget.setCurrentRow(row)

    def _remove_step(self) -> None:
        """Remove all selected steps after confirmation."""
        rows = self._selected_rows()
        if not rows:
            return
        answer = QMessageBox.question(
            self,
            "Delete Steps",
            f"Delete {len(rows)} selected step{'s' if len(rows) != 1 else ''}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._save_state()
        next_row = min(rows[0], max(0, len(self.steps) - len(rows) - 1))
        for row in reversed(rows):
            if 0 <= row < len(self.steps):
                del self.steps[row]
        self._refresh_list()
        if self.steps:
            self.list_widget.setCurrentRow(next_row)

    def _move_step(self, direction: int) -> None:
        """Move the selected step up or down by one slot."""
        row = self.list_widget.currentRow()
        new_row = row + direction
        if row < 0 or new_row < 0 or new_row >= len(self.steps):
            return
        self._save_state()
        self.steps[row], self.steps[new_row] = self.steps[new_row], self.steps[row]
        self._refresh_list()
        self.list_widget.setCurrentRow(new_row)

    def _selected_rows(self) -> list[int]:
        """Return selected step rows, falling back to the current row."""
        rows = sorted({self.list_widget.row(item) for item in self.list_widget.selectedItems()})
        if rows:
            return [row for row in rows if 0 <= row < len(self.steps)]
        row = self.list_widget.currentRow()
        return [row] if 0 <= row < len(self.steps) else []

    def _select_rows(self, rows) -> None:
        """Select a group of rows after a list rebuild."""
        self.list_widget.clearSelection()
        valid_rows = [row for row in rows if 0 <= int(row) < self.list_widget.count()]
        if valid_rows:
            self.list_widget.setCurrentRow(valid_rows[0])
        for row in valid_rows:
            item = self.list_widget.item(int(row))
            if item is not None:
                item.setSelected(True)

    def _save_state(self) -> None:
        """Store the current step list for undo before a mutation."""
        self.undo_stack.append(deepcopy(self.steps))
        self.redo_stack.clear()
        self._apply_history_state()

    def _undo(self) -> None:
        """Restore the previous editor step list."""
        if not self.undo_stack:
            return
        self.redo_stack.append(deepcopy(self.steps))
        self.steps = deepcopy(self.undo_stack.pop())
        self._refresh_list()
        self._apply_history_state()

    def _redo(self) -> None:
        """Reapply one undone editor step list."""
        if not self.redo_stack:
            return
        self.undo_stack.append(deepcopy(self.steps))
        self.steps = deepcopy(self.redo_stack.pop())
        self._refresh_list()
        self._apply_history_state()

    def _apply_history_state(self) -> None:
        """Enable undo/redo buttons when matching history exists."""
        self.undo_button.setEnabled(bool(self.undo_stack))
        self.redo_button.setEnabled(bool(self.redo_stack))

    def _apply_selection_state(self) -> None:
        """Enable step actions according to the current selection."""
        rows = self._selected_rows()
        has_selection = bool(rows)
        single_selection = len(rows) == 1
        current_row = rows[0] if single_selection else self.list_widget.currentRow()
        for button in (self.duplicate_button, self.remove_button):
            button.setEnabled(has_selection)
        self.edit_params_button.setEnabled(single_selection)
        self.update_button.setEnabled(single_selection)
        self.up_button.setEnabled(single_selection and current_row > 0)
        self.down_button.setEnabled(single_selection and 0 <= current_row < len(self.steps) - 1)
