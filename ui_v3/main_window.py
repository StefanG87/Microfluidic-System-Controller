"""Main window for the parallel PySide6/Fluent v3 GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from ui_v3.control_panel import ControlPanel
from ui_v3.controllers.runtime_controller import V3RuntimeController
from ui_v3.fluent_compat import apply_v3_palette
from ui_v3.navigation import NavigationSidebar
from ui_v3.plot_panel import PlotPanel
from ui_v3.status_bar import V3StatusBar


class V3MainWindow(QMainWindow):
    """Modern shell around the existing controller/runtime architecture."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Microfluidic System Controller v3")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)
        self.controller = V3RuntimeController(self)

        self.navigation = NavigationSidebar()
        self.control_panel = ControlPanel(self.controller)
        self.plot_panel = PlotPanel()
        self.status_strip = V3StatusBar()

        self._build_layout()
        self._connect_signals()
        self._install_shortcuts()
        apply_v3_palette(self)
        QTimer.singleShot(300, self._auto_connect_hardware)

    def _build_layout(self) -> None:
        """Build the engineering-style three-zone layout."""
        root = QWidget()
        root.setObjectName("V3Root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.navigation.setMinimumWidth(56)
        self.navigation.setMaximumWidth(56)
        self.control_panel.setMinimumWidth(340)
        self.control_panel.setMaximumWidth(500)
        self.plot_panel.setMinimumWidth(560)
        body_layout.addWidget(self.navigation)
        body_layout.addWidget(self.control_panel, 1)
        body_layout.addWidget(self.plot_panel, 2)

        root_layout.addWidget(body, 1)
        root_layout.addWidget(self.status_strip)
        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        """Wire route changes and runtime updates."""
        self.navigation.route_requested.connect(self.control_panel.set_route)
        self.controller.status_changed.connect(self.status_strip.update_status)
        self.controller.status_changed.connect(self._update_target_trace)
        self.controller.measurement_state_changed.connect(lambda active: self.plot_panel.reset() if active else None)
        self.controller.sample_ready.connect(self.plot_panel.append_sample)
        self.controller.device_catalog_changed.connect(self._handle_device_catalog_changed)
        self.controller.log_message.connect(self.plot_panel.append_log)
        self.plot_panel.set_device_catalog(self.controller.device_catalog.to_embedded_editor_info())

    def _install_shortcuts(self) -> None:
        """Install the classic global shortcuts that are safe in v3."""
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)
        QShortcut(QKeySequence.Save, self, activated=self._export_shortcut)

    def _export_shortcut(self) -> None:
        """Export current measurement data via Ctrl+S when data exists."""
        if not self.controller.measurement_has_data():
            self.controller.append_log("[v3] Ctrl+S ignored: no measurement samples available.")
            return
        self.controller.export_csv()

    def _update_target_trace(self, status: dict) -> None:
        """Keep the plot target line aligned with the controller target."""
        self.plot_panel.update_target(float(status.get("target_pressure", 0.0) or 0.0))

    def _handle_device_catalog_changed(self, catalog_info: dict) -> None:
        """Refresh plot state after profile/config changes to avoid stale channel traces."""
        self.plot_panel.reset()
        self.plot_panel.set_device_catalog(catalog_info)

    def _auto_connect_hardware(self) -> None:
        """Try the saved hardware connection once after the window is visible."""
        if self.controller.hardware_connected:
            return
        self.controller.append_log("[v3] Auto-connecting hardware using saved settings...")
        self.controller.connect_hardware()

    def closeEvent(self, event) -> None:
        """Reset lab hardware to a safe state before the v3 window closes."""
        self.controller.shutdown_for_close()
        event.accept()
