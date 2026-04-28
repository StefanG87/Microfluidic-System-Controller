"""Entry point for the parallel PySide6/Fluent v3 controller GUI."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
MODULES_DIR = os.path.join(PROJECT_ROOT, "modules")


def _bootstrap_runtime_paths() -> None:
    """Make the project root and bundled local SDK modules importable."""
    for path in (PROJECT_ROOT, MODULES_DIR):
        if path not in sys.path:
            sys.path.insert(0, path)


_bootstrap_runtime_paths()

from PySide6.QtWidgets import QApplication

from ui_v3.fluent_compat import Theme, setTheme
from ui_v3.main_window import V3MainWindow


def main() -> int:
    """Create the Qt6 application, show the v3 main window, and start the event loop."""
    app = QApplication(sys.argv)
    app.setApplicationName("Microfluidic System Controller v3")
    setTheme(Theme.DARK)
    window = V3MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
