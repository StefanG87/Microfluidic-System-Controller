"""Main window for the parallel PySide6/Fluent v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from ui_v3.control_panel import ControlPanel
from ui_v3.controllers.runtime_controller import V3RuntimeController
from ui_v3.fluent_compat import apply_dark_palette
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
        apply_dark_palette(self)

    def _build_layout(self) -> None:
        """Build the engineering-style three-zone layout."""
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.navigation.setMinimumWidth(210)
        self.navigation.setMaximumWidth(260)
        self.control_panel.setMinimumWidth(360)
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

    def _update_target_trace(self, status: dict) -> None:
        """Keep the plot target line aligned with the controller target."""
        self.plot_panel.update_target(float(status.get("target_pressure", 0.0) or 0.0))
