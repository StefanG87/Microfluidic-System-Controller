"""Worker object that runs automation programs off the GUI thread."""

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

    def run(self):
        """Start the program runner inside the worker thread."""
        try:
            self.running = True
            self.runner.run_program(log_callback=self.log_message.emit)
            if self.running:
                self.finished.emit()
        except Exception as e:
            self.error.emit(f"Program error:\n{str(e)}")
        finally:
            self.running = False

    def stop(self):
        """Stop the program runner and emit the stopped signal."""
        self.running = False
        self.runner.stop()
        self.stopped.emit("Program execution stopped.")