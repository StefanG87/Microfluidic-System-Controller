"""Page stack containing the v3 control cards."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from ui_v3.cards import ExportCard, PressureCard, ProgramCard, SamplingCard, SensorCard, SettingsCard, ValveCard
from ui_v3.fluent_compat import SubtitleLabel


class ControlPanel(QStackedWidget):
    """Route-keyed stack of control pages used by MainWindow."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._routes = {}
        self._build_pages()

    def set_route(self, route: str) -> None:
        """Switch to a route if it exists."""
        widget = self._routes.get(route)
        if widget is not None:
            self.setCurrentWidget(widget)

    def _build_pages(self) -> None:
        """Create the first set of v3 pages."""
        self._add_page(
            "dashboard",
            "Dashboard",
            [
                PressureCard(self.controller),
                SensorCard(self.controller),
                SamplingCard(self.controller),
                ExportCard(self.controller),
            ],
        )
        self._add_page(
            "pressure",
            "Pressure Control",
            [PressureCard(self.controller), SensorCard(self.controller), SamplingCard(self.controller)],
        )
        self._add_page("valves", "Valves", [ValveCard(self.controller)])
        self._add_page("program", "Program Runner", [ProgramCard(self.controller)])
        self._add_page("settings", "Settings", [SettingsCard(self.controller), ValveCard(self.controller)])

    def _add_page(self, route: str, title: str, cards: list[QWidget]) -> None:
        """Add a scrollable card page."""
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel(title))
        for card in cards:
            layout.addWidget(card)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        self.addWidget(scroll)
        self._routes[route] = scroll
