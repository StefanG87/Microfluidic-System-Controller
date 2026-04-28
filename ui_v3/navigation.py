"""Navigation sidebar for the v3 desktop UI."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal

from ui_v3.fluent_compat import NavigationInterface, NavigationItemPosition, fluent_icon


@dataclass(frozen=True)
class NavigationItem:
    """One route shown in the v3 navigation sidebar."""

    route: str
    title: str
    icon: str
    position: object = NavigationItemPosition.TOP


NAV_ITEMS = (
    NavigationItem("dashboard", "Dashboard", "HOME"),
    NavigationItem("pressure", "Pressure Control", "SPEED_HIGH"),
    NavigationItem("valves", "Valves", "ROBOT"),
    NavigationItem("program", "Program Runner", "PLAY"),
    NavigationItem("settings", "Settings", "SETTING", NavigationItemPosition.BOTTOM),
)


class NavigationSidebar(NavigationInterface):
    """Fluent navigation surface that emits stable route keys."""

    route_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent, showMenuButton=True)
        self.setObjectName("V3NavigationSidebar")
        self._buttons = {}
        for item in NAV_ITEMS:
            self._add_route(item)

    def _add_route(self, item: NavigationItem) -> None:
        """Add one route without coupling page construction to this widget."""
        button = self.addItem(
            item.route,
            fluent_icon(item.icon),
            item.title,
            lambda checked=False, route=item.route: self.route_requested.emit(route),
            position=item.position,
            tooltip=item.title,
        )
        self._buttons[item.route] = button
