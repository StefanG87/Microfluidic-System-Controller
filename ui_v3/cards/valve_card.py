"""Valve card for the v3 GUI."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QWidget

from ui_v3.fluent_compat import BodyLabel, CardWidget, CaptionLabel, PushButton, make_card_layout


class ValveCard(CardWidget):
    """Expose profile-defined valves as dynamic toggle buttons."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._buttons = {}
        layout = make_card_layout(self)
        layout.addWidget(BodyLabel("Valves"))
        layout.addWidget(CaptionLabel("Valve names come from the active hardware profile/catalog."))

        self.button_area = QWidget()
        self.grid = QGridLayout(self.button_area)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        layout.addWidget(self.button_area)

        self.close_all = PushButton("Close All Valves")
        self.close_all.clicked.connect(lambda _checked=False: controller.close_all_valves())
        layout.addWidget(self.close_all)

        controller.device_catalog_changed.connect(self._rebuild)
        self._rebuild(controller.device_catalog.to_embedded_editor_info())

    def _rebuild(self, catalog_info: dict) -> None:
        """Rebuild buttons when the device catalog changes."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons.clear()

        valve_names = list(catalog_info.get("valve_names", []))
        if not valve_names:
            self.grid.addWidget(CaptionLabel("No valves in the current catalog."), 0, 0)
            return

        for index, name in enumerate(valve_names):
            button = PushButton(name)
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, valve_name=name, btn=button: self._set_valve(valve_name, checked, btn)
            )
            self._buttons[name] = button
            self.grid.addWidget(button, index // 2, index % 2)

    def _set_valve(self, valve_name: str, checked: bool, button) -> None:
        """Forward the valve command and roll the UI back if the command was rejected."""
        ok = self.controller.set_valve_state_by_name(valve_name, bool(checked))
        if not ok:
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)
            self.controller.append_log(f"[v3] Valve not available: {valve_name}")
