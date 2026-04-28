"""Sampling control card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QSpinBox

from ui_v3.fluent_compat import BodyLabel, CardWidget, CaptionLabel, PrimaryPushButton, PushButton, make_card_layout, stretch_row


class SamplingCard(CardWidget):
    """Configure sampling interval and measurement state."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = make_card_layout(self)
        layout.addWidget(BodyLabel("Sampling"))
        layout.addWidget(CaptionLabel("All intervals are stored and displayed in milliseconds."))

        self.interval = QSpinBox()
        self.interval.setRange(1, 600000)
        self.interval.setValue(controller.sampling_interval_ms)
        self.interval.setSuffix(" ms")
        self.interval.valueChanged.connect(controller.set_sampling_interval_ms)

        self.start_button = PrimaryPushButton("Start Measurement")
        self.stop_button = PushButton("Stop Measurement")
        self.start_button.clicked.connect(lambda _checked=False: controller.start_measurement())
        self.stop_button.clicked.connect(lambda _checked=False: controller.stop_measurement())

        layout.addWidget(self.interval)
        layout.addWidget(stretch_row(self.start_button, self.stop_button))
        controller.status_changed.connect(self._apply_status)

    def _apply_status(self, status: dict) -> None:
        """Keep interval and button state aligned with runtime state."""
        self.interval.blockSignals(True)
        self.interval.setValue(int(status.get("sampling_interval_ms", self.interval.value()) or 1))
        self.interval.blockSignals(False)
        measuring = bool(status.get("measuring"))
        self.start_button.setEnabled(not measuring)
        self.stop_button.setEnabled(measuring)
