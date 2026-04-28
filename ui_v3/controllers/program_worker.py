"""PySide6 worker wrapper for automation programs in the v3 GUI."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, Signal


class V3ProgramWorker(QObject):
    """Run a ProgramRunner instance off the GUI thread using Qt6 signals."""

    finished = Signal()
    error = Signal(str)
    stopped = Signal(str)
    log_message = Signal(str)

    def __init__(self, runner):
        super().__init__()
        self.runner = runner
        self._stop_requested = False

    def run(self) -> None:
        """Execute the loaded program."""
        try:
            self._stop_requested = False
            self.runner.run_program(log_callback=self.log_message.emit)
            if self._stop_requested:
                self.stopped.emit("Program execution stopped.")
        except Exception:
            self.error.emit("Program error:\n" + traceback.format_exc())
        finally:
            self.finished.emit()

    def stop(self) -> None:
        """Request cancellation; the runner stops after the current abortable step returns."""
        self._stop_requested = True
        self.runner.stop()
