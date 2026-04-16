"""Worker object that runs automation programs off the GUI thread."""

import traceback

from PyQt5.QtCore import QObject, pyqtSignal


class ProgramWorker(QObject):
    """Bridge a ProgramRunner into a Qt worker object with status signals."""

    finished = pyqtSignal()
    error = pyqtSignal(str)
    stopped = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, runner):
        super().__init__()
        self.runner = runner
        self.running = False
        self._stop_requested = False

    def run(self):
        """Start the program runner inside the worker thread."""
        try:
            self.running = True
            self._stop_requested = False
            self.runner.run_program(log_callback=self.log_message.emit)
            if self._stop_requested:
                self.stopped.emit("Program execution stopped.")
        except Exception:
            self.error.emit("Program error:\n" + traceback.format_exc())
        finally:
            self.running = False
            self.finished.emit()

    def stop(self):
        """Request program cancellation; the worker finishes after the current step returns."""
        self._stop_requested = True
        self.running = False
        self.runner.stop()
