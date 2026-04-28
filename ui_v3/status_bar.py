"""Compact status strip for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout

from ui_v3.fluent_compat import BodyLabel, CaptionLabel


class V3StatusBar(QFrame):
    """Show connection, measurement, program, profile, and sampling state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("V3StatusBar")
        self.connection = CaptionLabel("Disconnected")
        self.measurement = CaptionLabel("Idle")
        self.program = CaptionLabel("Program idle")
        self.profile = CaptionLabel("Profile: -")
        self.interval = CaptionLabel("Interval: - ms")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(18)
        layout.addWidget(BodyLabel("MF Controller v3"))
        layout.addStretch(1)
        for label in (self.connection, self.measurement, self.program, self.profile, self.interval):
            layout.addWidget(label)

    def update_status(self, status: dict) -> None:
        """Apply one status snapshot emitted by the runtime controller."""
        self.connection.setText("Connected" if status.get("connected") else "Disconnected")
        self.measurement.setText("Measuring" if status.get("measuring") else "Idle")
        self.program.setText("Program running" if status.get("program_running") else "Program idle")
        self.profile.setText(f"Profile: {status.get('profile') or '-'}")
        self.interval.setText(f"Interval: {status.get('sampling_interval_ms', '-')} ms")
