"""CSV export card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFileDialog

from ui_v3.fluent_compat import (
    CardWidget,
    CaptionLabel,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    add_info_header,
    compact_tooltip,
    make_card_layout,
    mark_primary_action,
    stretch_row,
)


class ExportCard(CardWidget):
    """Export the current MeasurementSession through the runtime controller."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = make_card_layout(self)
        add_info_header(
            layout,
            "CSV Export",
            "Exports the current measurement buffer to CSV. The exporter includes pressure, flow, Fluigent sensors, valve states, rotary state, and registered future measurement channels when available.",
        )

        self.prefix = LineEdit()
        self.prefix.setPlaceholderText("measurement")
        self.prefix.editingFinished.connect(self._save_prefix)
        self.auto_button = mark_primary_action(PrimaryPushButton("Export with Timestamp"))
        self.choose_button = PushButton("Choose Path")
        self.read_timing_checkbox = QCheckBox("Include read timing metadata")
        self.read_timing_checkbox.setToolTip(
            compact_tooltip(
                "Adds sample duration and per-channel read timing columns to CSV exports. "
                "Keep this off for compact routine files; turn it on for methods validation or timing-sensitive experiments."
            )
        )
        self.auto_button.clicked.connect(lambda _checked=False: self._export_auto())
        self.choose_button.clicked.connect(lambda _checked=False: self._export_with_dialog())
        self.read_timing_checkbox.toggled.connect(
            lambda checked: self.controller.set_include_read_timing(bool(checked), persist=True)
        )
        layout.addWidget(CaptionLabel("Filename prefix"))
        layout.addWidget(self.prefix)
        layout.addWidget(stretch_row(self.auto_button, self.choose_button))
        layout.addWidget(self.read_timing_checkbox)
        controller.status_changed.connect(self._apply_status)
        self._apply_status(controller.status_snapshot())

    def _apply_status(self, status: dict) -> None:
        """Keep export options aligned with persisted controller settings."""
        self.read_timing_checkbox.blockSignals(True)
        self.read_timing_checkbox.setChecked(bool(status.get("include_read_timing", False)))
        self.read_timing_checkbox.blockSignals(False)
        current_prefix = str(status.get("export_prefix") or "measurement")
        if not self.prefix.hasFocus() and self.prefix.text() != current_prefix:
            self.prefix.setText(current_prefix)

    def _save_prefix(self) -> None:
        """Persist the prefix used for automatic timestamped exports."""
        prefix = self.controller.set_export_prefix(self.prefix.text(), persist=True)
        self.prefix.setText(prefix)

    def _export_auto(self) -> None:
        """Export to the standard measurements folder."""
        if not self.controller.measurement_has_data():
            self.controller.append_log("[v3] CSV export skipped: no samples available yet.")
            return
        try:
            self._save_prefix()
            self.controller.export_csv()
        except Exception as exc:
            self.controller.append_log(f"[v3] CSV export failed: {exc}")

    def _export_with_dialog(self) -> None:
        """Let the user choose the CSV path."""
        if not self.controller.measurement_has_data():
            self.controller.append_log("[v3] CSV export skipped: no samples available yet.")
            return
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            self.controller.suggest_csv_path(self.prefix.text().strip() or None),
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return
        try:
            self._save_prefix()
            self.controller.export_csv(path)
        except Exception as exc:
            self.controller.append_log(f"[v3] CSV export failed: {exc}")
