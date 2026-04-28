"""CSV export card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from ui_v3.fluent_compat import BodyLabel, CardWidget, CaptionLabel, PrimaryPushButton, PushButton, make_card_layout, stretch_row


class ExportCard(CardWidget):
    """Export the current MeasurementSession through the runtime controller."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = make_card_layout(self)
        layout.addWidget(BodyLabel("CSV Export"))
        layout.addWidget(CaptionLabel("Uses the shared CSV exporter and dynamic channel metadata."))

        self.auto_button = PrimaryPushButton("Export Automatically")
        self.choose_button = PushButton("Choose Path")
        self.auto_button.clicked.connect(lambda _checked=False: self._export_auto())
        self.choose_button.clicked.connect(lambda _checked=False: self._export_with_dialog())
        layout.addWidget(stretch_row(self.auto_button, self.choose_button))

    def _export_auto(self) -> None:
        """Export to the standard measurements folder."""
        try:
            self.controller.export_csv()
        except Exception as exc:
            self.controller.append_log(f"[v3] CSV export failed: {exc}")

    def _export_with_dialog(self) -> None:
        """Let the user choose the CSV path."""
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            "",
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return
        try:
            self.controller.export_csv(path)
        except Exception as exc:
            self.controller.append_log(f"[v3] CSV export failed: {exc}")
