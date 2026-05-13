"""Page stack containing the v3 control cards."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from ui_v3.cards import ExportCard, HardwareCard, PressureCard, ProgramCard, RotaryCard, SamplingCard, SensorCard, SettingsCard, ValveCard
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
                PressureCard(self.controller, compact_status=True),
                SamplingCard(self.controller, show_interval=False),
                ProgramCard(self.controller, compact=True, show_log=False),
                SensorCard(self.controller),
                ValveCard(self.controller, dashboard_mode=True),
                RotaryCard(self.controller),
            ],
            scroll=False,
            show_title=False,
        )
        self._add_page(
            "pressure",
            "Pressure Control",
            [
                PressureCard(self.controller),
                SettingsCard(self.controller, show_profile=False, show_pressure_offset=True),
                SensorCard(self.controller),
            ],
            scroll=False,
        )
        self._add_page("valves", "Valves", [ValveCard(self.controller)], scroll=False)
        self._add_page("program", "Program Runner", [ProgramCard(self.controller)])
        self._add_page(
            "settings",
            "Settings",
            [
                HardwareCard(self.controller),
                SettingsCard(self.controller, show_profile=True, show_pressure_offset=False),
                SamplingCard(self.controller),
                ExportCard(self.controller),
                SensorCard(self.controller),
            ],
            scroll=True,
        )

    def _add_page(
        self,
        route: str,
        title: str,
        cards: list[QWidget],
        scroll: bool = True,
        show_title: bool = True,
    ) -> None:
        """Add a scrollable card page."""
        content = QWidget()
        layout = QVBoxLayout(content)
        margin = 6 if route == "dashboard" else 10
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(4 if route == "dashboard" else 6)
        if show_title:
            layout.addWidget(SubtitleLabel(title))
        for card in cards:
            layout.addWidget(card)
        layout.addStretch(1)

        if not scroll:
            self.addWidget(content)
            self._routes[route] = content
            return

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        self.addWidget(scroll)
        self._routes[route] = scroll
