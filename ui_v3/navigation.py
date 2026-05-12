"""Compact icon navigation sidebar for the v3 desktop UI."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui_v3.fluent_compat import ToolButton, fluent_icon


@dataclass(frozen=True)
class NavigationItem:
    """One route shown in the v3 navigation sidebar."""

    route: str
    title: str
    icon: str


NAV_ITEMS = (
    NavigationItem("dashboard", "Dashboard", "HOME"),
    NavigationItem("pressure", "Pressure", "SPEED_HIGH"),
    NavigationItem("valves", "Valves", "TECHNICAL_VALVE"),
    NavigationItem("program", "Programs", "PLAY"),
    NavigationItem("settings", "Settings", "SETTING"),
)


def technical_valve_icon() -> QIcon:
    """Draw a compact P&ID-style valve symbol for the valve page."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor("#18202b"), 2.2)
    painter.setPen(pen)
    painter.setBrush(QColor("#f8fbfc"))

    left_triangle = QPolygonF([QPointF(6, 10), QPointF(16, 16), QPointF(6, 22)])
    right_triangle = QPolygonF([QPointF(26, 10), QPointF(16, 16), QPointF(26, 22)])
    painter.drawPolygon(left_triangle)
    painter.drawPolygon(right_triangle)
    painter.drawLine(16, 16, 16, 6)
    painter.drawRect(11, 3, 10, 4)
    painter.drawLine(2, 16, 6, 16)
    painter.drawLine(26, 16, 30, 16)
    painter.end()

    return QIcon(pixmap)


class NavigationSidebar(QWidget):
    """Icon rail with tooltips; keeps the main cockpit width close to v2."""

    route_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("V3NavigationSidebar")
        self._buttons = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(10)

        for item in NAV_ITEMS:
            button = ToolButton()
            icon = technical_valve_icon() if item.icon == "TECHNICAL_VALVE" else fluent_icon(item.icon)
            button.setIcon(icon)
            button.setIconSize(QSize(20, 20))
            button.setToolTip(item.title)
            button.setCheckable(True)
            button.setFixedSize(40, 40)
            button.clicked.connect(lambda _checked=False, route=item.route: self._select_route(route))
            layout.addWidget(button)
            self._buttons[item.route] = button

        layout.addStretch(1)
        self._select_route("dashboard", emit=False)

    def _select_route(self, route: str, emit: bool = True) -> None:
        """Mark the active route and optionally notify the main window."""
        for key, button in self._buttons.items():
            button.blockSignals(True)
            button.setChecked(key == route)
            button.blockSignals(False)
        if emit:
            self.route_requested.emit(route)
