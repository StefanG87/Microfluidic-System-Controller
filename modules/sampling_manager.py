import time
from PyQt5.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox, QPushButton, QVBoxLayout


class SamplingManager:
    """Central time base and export accessor for the active measurement session."""

    def __init__(self):
        self.sampling_rate_ms = 1000
        self._t0_epoch = None
        self._t0_mono = None
        self.start_timestamp = None

    def set_sampling_rate(self, rate_ms):
        self.sampling_rate_ms = rate_ms

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

    def get_all_data(self):
        """
        Collect the current GUI buffers for CSV export.
        `time_data` contains absolute epoch timestamps.
        """
        gui = QApplication.instance().main_window
        return (
            list(getattr(gui, "abs_time_data", [])),
            list(gui.target_data),
            list(gui.corrected_data),
            list(gui.measured_data),
            list(gui.valve_states),
            [list(ch) for ch in gui.flow_data],
            [list(ch) for ch in gui.fluigent_pressure_data],
            gui.sampling_rate,
            self.start_timestamp,
        )


sampling_manager = SamplingManager()


class SamplingDialog(QDialog):
    """Dialog for editing the sampling interval used by the live timer."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Sampling Rate")

        self.parent = parent
        layout = QVBoxLayout(self)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Sampling rate [ms]")
        self.input.setText(str(self.parent.sampling_rate))
        layout.addWidget(self.input)

        btn = QPushButton("Apply Sampling Rate")
        btn.clicked.connect(self.apply_rate)
        layout.addWidget(btn)

    def apply_rate(self):
        """Apply a validated sampling interval to the parent timer."""
        try:
            rate = int(self.input.text())
            if rate <= 0:
                raise ValueError("Sampling rate must be positive.")

            if hasattr(self.parent, "set_sampling_rate_ms"):
                self.parent.set_sampling_rate_ms(rate)
            else:
                self.parent.sampling_rate = rate
                self.parent.timer.setInterval(rate)
                sampling_manager.set_sampling_rate(rate)

            self.close()
        except Exception:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid positive integer.")
