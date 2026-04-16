"""Entry point for the main microfluidic controller GUI."""

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

from PyQt5.QtWidgets import QApplication

from modules.gui_window import PressureFlowGUI


def _apply_global_style(app: QApplication) -> None:
    """Apply the shared button styling used by the desktop GUI."""
    app.setStyleSheet(
        """
        QPushButton {
            background-color: #f0f0f0;
            border: 1px solid #999;
            border-radius: 5px;
            padding: 3px;
        }

        QPushButton:hover {
            background-color: #E3BB8F;
        }
        QPushButton:pressed {
            background-color: #F08F1A;
        }
        QPushButton:checked {
            background-color: #F08F1A;
            border: 2px solid #C26C10;
        }
        QPushButton:disabled {
            background-color: #e0e0e0;
            color: #999;
        }
        QToolButton {
            background-color: #f9f9f9;
            border: 1px solid #aaa;
            border-radius: 6px;
            padding: 4px;
        }
        QToolButton:hover {
            background-color: #E3BB8F;
        }
        QToolButton:pressed {
            background-color: #F08F1A;
        }
        """
    )


def main() -> int:
    """Create the Qt application, show the main window, and start the event loop."""
    app = QApplication(sys.argv)
    _apply_global_style(app)
    window = PressureFlowGUI()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
