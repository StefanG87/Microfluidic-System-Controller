"""Page stack containing the v3 control cards."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from modules.device_catalog import SENSOR_KIND_FLUIGENT_PRESSURE, SENSOR_KIND_INTERNAL_PRESSURE
from ui_v3.cards import (
    BalanceConnectionCard,
    ExportCard,
    HardwareCard,
    PlotSettingsCard,
    PressureCard,
    ProgramCard,
    RotaryCard,
    RotaryConnectionCard,
    SamplingCard,
    SensorCard,
    SettingsCard,
    ValveCard,
)
from ui_v3.calibration_tab import MediumCalibrationTab, hardware_context_from_controller
from ui_v3.fluent_compat import SubtitleLabel


class ControlPanel(QStackedWidget):
    """Route-keyed stack of control pages used by MainWindow."""

    def __init__(self, controller, plot_panel=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.plot_panel = plot_panel
        self._routes = {}
        self._build_pages()
        self.controller.device_catalog_changed.connect(self._sync_calibration_hardware)

    def set_route(self, route: str) -> None:
        """Switch to a route if it exists."""
        widget = self._routes.get(route)
        if widget is not None:
            self.setCurrentWidget(widget)

    def _build_pages(self) -> None:
        """Create the first set of v3 pages."""
        self._rotary_card = RotaryCard(self.controller, show_connection_controls=False)
        self._add_page(
            "dashboard",
            "Dashboard",
            [
                PressureCard(self.controller, compact_status=True),
                SamplingCard(self.controller, show_interval=False),
                ProgramCard(self.controller, compact=True, show_log=False),
                SensorCard(self.controller, compact=True),
                ValveCard(self.controller, dashboard_mode=True, show_header=False),
                self._rotary_card,
            ],
            scroll=False,
            show_title=False,
        )
        self._add_page(
            "pressure",
            "Pressure Control",
            [
                PressureCard(self.controller),
                SensorCard(
                    self.controller,
                    title="Pressure Sensor Values",
                    description=(
                        "Shows the latest internal pressure-controller readout and all detected "
                        "Fluigent pressure sensors. Flow, balance, and valve channels stay on the "
                        "Dashboard, Settings, and Plot Settings pages."
                    ),
                    sensor_kinds={SENSOR_KIND_INTERNAL_PRESSURE, SENSOR_KIND_FLUIGENT_PRESSURE},
                ),
                ValveCard(self.controller),
                SettingsCard(self.controller, show_profile=False, show_pressure_offset=True),
            ],
            scroll=True,
        )
        self._add_page("valves", "Valves", [ValveCard(self.controller)], scroll=True)
        self._add_page("program", "Program Runner", [ProgramCard(self.controller)])
        if self.plot_panel is not None:
            self._add_page("plot_settings", "Plot Settings", [PlotSettingsCard(self.plot_panel)], scroll=True)
        self._calibration_tab = MediumCalibrationTab(
            hardware=hardware_context_from_controller(self.controller),
            hardware_provider=lambda: hardware_context_from_controller(self.controller),
        )
        self._add_page("calibration", "Calibration", [self._calibration_tab], scroll=False)
        self._add_page(
            "settings",
            "Settings",
            [
                HardwareCard(self.controller),
                RotaryConnectionCard(self.controller),
                BalanceConnectionCard(self.controller),
                SettingsCard(self.controller, show_profile=True, show_pressure_offset=False),
                SamplingCard(self.controller, show_controls=False),
                ExportCard(self.controller),
                SensorCard(self.controller),
            ],
            scroll=True,
        )

    def _sync_calibration_hardware(self, _catalog_info=None) -> None:
        """Keep the calibration tab aligned with hardware/profile changes."""
        tab = getattr(self, "_calibration_tab", None)
        if tab is not None:
            tab.set_hardware_context(hardware_context_from_controller(self.controller))

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
