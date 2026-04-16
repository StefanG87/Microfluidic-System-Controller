import time
from PyQt5.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from modules.measurement_session import ExportSnapshot


class SamplingManager:
    """Central time base and export accessor for the active measurement session."""

    def __init__(self):
        self.sampling_interval_ms = 1000
        self.sampling_rate_ms = self.sampling_interval_ms  # Legacy alias for older callers.
        self._t0_epoch = None
        self._t0_mono = None
        self.start_timestamp = None

    def set_sampling_interval_ms(self, interval_ms):
        """Store the active sampling interval in milliseconds."""
        interval_ms = max(1, int(interval_ms))
        self.sampling_interval_ms = interval_ms
        self.sampling_rate_ms = interval_ms

    def set_sampling_rate(self, rate_ms):
        """Backward-compatible wrapper for older code using the rate name."""
        self.set_sampling_interval_ms(rate_ms)

    def reset_time(self):
        """Reset the shared time base for a new measurement or program run."""
        self._t0_epoch = time.time()
        self._t0_mono = time.monotonic()
        self.start_timestamp = self._t0_epoch

    def get_timestamps(self):
        """Return `(absolute_epoch_seconds, relative_seconds)` from one monotonic delta."""
        if self._t0_mono is None or self._t0_epoch is None:
            self.reset_time()
        rel = time.monotonic() - self._t0_mono
        abs_ts = self._t0_epoch + rel
        return abs_ts, rel

    def get_export_snapshot(self):
        """Collect the current GUI buffers as an ExportSnapshot for CSV export."""
        gui = QApplication.instance().main_window
        sampling_interval_ms = getattr(gui, "sampling_interval_ms", getattr(gui, "sampling_rate", self.sampling_interval_ms))
        session = getattr(gui, "measurement_session", None)
        if session is not None:
            return session.snapshot_for_export(sampling_interval_ms, self.start_timestamp)
        return ExportSnapshot(
            time_data=list(getattr(gui, "abs_time_data", [])),
            target_data=list(gui.target_data),
            corrected_data=list(gui.corrected_data),
            measured_data=list(gui.measured_data),
            valve_states=list(gui.valve_states),
            flow_data=[list(ch) for ch in gui.flow_data],
            fluigent_data=[list(ch) for ch in gui.fluigent_pressure_data],
            sampling_interval_ms=sampling_interval_ms,
            start_timestamp=self.start_timestamp,
            rotary_active=list(getattr(gui, "rotary_active", [])),
        )

    def get_all_data(self):
        """
        Collect the current GUI buffers for legacy CSV export callers.
        `time_data` contains absolute epoch timestamps.
        """
        return self.get_export_snapshot().as_legacy_tuple()


sampling_manager = SamplingManager()


class SamplingDialog(QDialog):
    """Dialog for editing the sampling interval used by the live timer."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Sampling Interval")

        self.parent = parent
        layout = QVBoxLayout(self)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Sampling interval [ms]")
        current_interval_ms = getattr(self.parent, "sampling_interval_ms", getattr(self.parent, "sampling_rate", sampling_manager.sampling_interval_ms))
        self.input.setText(str(current_interval_ms))
        layout.addWidget(self.input)

        btn = QPushButton("Apply Sampling Interval")
        btn.clicked.connect(self.apply_rate)
        layout.addWidget(btn)

    def apply_rate(self):
        """Apply a validated sampling interval to the parent timer."""
        try:
            interval_ms = int(self.input.text())
            if interval_ms <= 0:
                raise ValueError("Sampling interval must be positive.")

            if hasattr(self.parent, "set_sampling_interval_ms"):
                self.parent.set_sampling_interval_ms(interval_ms)
            elif hasattr(self.parent, "set_sampling_rate_ms"):
                self.parent.set_sampling_rate_ms(interval_ms)
            else:
                self.parent.sampling_interval_ms = interval_ms
                self.parent.sampling_rate = interval_ms  # Legacy alias.
                self.parent.timer.setInterval(interval_ms)
                sampling_manager.set_sampling_interval_ms(interval_ms)

            self.close()
        except Exception:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid positive integer.")
