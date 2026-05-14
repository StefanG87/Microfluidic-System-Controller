"""Valve card for the v3 GUI."""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtWidgets import QGridLayout, QGroupBox, QPushButton, QVBoxLayout, QWidget

from ui_v3.fluent_compat import CardWidget, CaptionLabel, PushButton, add_info_header, make_card_layout


class ValveCard(CardWidget):
    """Expose profile-defined valves as dynamic toggle buttons."""

    def __init__(self, controller, parent=None, dashboard_mode: bool = False, show_header: bool = True):
        super().__init__(parent)
        self.controller = controller
        self.dashboard_mode = bool(dashboard_mode)
        self.show_header = bool(show_header)
        self._buttons = {}
        self._groups = []
        layout = make_card_layout(self, compact=self.dashboard_mode)
        if self.show_header:
            add_info_header(
                layout,
                "Valves",
                "Toggles profile-defined Modbus valve coils. Active valves are highlighted with the shared v3 accent color. "
                "Close All Valves closes every configured valve without changing pressure.",
            )

        self.button_area = QWidget()
        self.group_layout = QVBoxLayout(self.button_area)
        self.group_layout.setContentsMargins(0, 0, 0, 0)
        self.group_layout.setSpacing(2 if self.dashboard_mode else 4)
        layout.addWidget(self.button_area)

        self.close_all = PushButton("Close All Valves")
        self.close_all.clicked.connect(lambda _checked=False: controller.close_all_valves())
        layout.addWidget(self.close_all)

        controller.device_catalog_changed.connect(self._rebuild)
        controller.status_changed.connect(self._apply_status)
        self._rebuild(controller.device_catalog.to_embedded_editor_info())
        self._apply_status(controller.status_snapshot())

    def _rebuild(self, catalog_info: dict) -> None:
        """Rebuild buttons when the device catalog changes."""
        while self.group_layout.count():
            item = self.group_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons.clear()
        self._groups.clear()

        valve_items = self._valve_items(catalog_info)
        if self.dashboard_mode:
            valve_items = self._dashboard_valve_items(valve_items)
        if not valve_items:
            self.group_layout.addWidget(CaptionLabel("No valves in the current catalog."))
            return

        grouped = OrderedDict()
        for item in valve_items:
            grouped.setdefault(item["box"], []).append(item)

        for box_title, items in grouped.items():
            group = QGroupBox(box_title)
            group.setObjectName("V3ValveGroup")
            grid = QGridLayout(group)
            margin = 4 if self.dashboard_mode else 6
            grid.setContentsMargins(margin, margin, margin, margin)
            grid.setHorizontalSpacing(4 if self.dashboard_mode else 6)
            grid.setVerticalSpacing(2 if self.dashboard_mode else 4)
            column_count = 3 if len(items) >= 9 else 2

            for index, item in enumerate(items):
                command_name = item["name"]
                button = QPushButton(item["button_label"])
                button.setObjectName("V3ValveButton")
                button.setProperty("valveActive", False)
                button.setProperty("valveGroup", item["group"])
                button.setCheckable(True)
                button.setMinimumHeight(24 if self.dashboard_mode else 28)
                button.setToolTip(command_name)
                button.clicked.connect(
                    lambda checked=False, valve_name=command_name, btn=button: self._set_valve(valve_name, checked, btn)
                )
                self._buttons[command_name] = button
                grid.addWidget(button, index // column_count, index % column_count)

            self._groups.append(group)
            self.group_layout.addWidget(group)

    @staticmethod
    def _valve_items(catalog_info: dict) -> list[dict]:
        """Return v2-style valve display metadata from the runtime catalog."""
        descriptors = list(catalog_info.get("valve_descriptors", []))
        items = []
        for descriptor in descriptors:
            if not isinstance(descriptor, dict):
                continue
            name = str(descriptor.get("name", "")).strip()
            metadata = descriptor.get("metadata", {})
            metadata = metadata if isinstance(metadata, dict) else {}
            if not name:
                continue
            items.append(
                {
                    "name": name,
                    "group": str(metadata.get("group") or "").lower(),
                    "box": str(metadata.get("box") or "Valves"),
                    "button_label": str(metadata.get("button_label") or name),
                }
            )

        if items:
            return items

        return [
            {
                "name": str(name),
                "group": "",
                "box": "Valves",
                "button_label": str(name),
            }
            for name in catalog_info.get("valve_names", [])
            if str(name).strip()
        ]

    @staticmethod
    def _dashboard_valve_items(items: list[dict]) -> list[dict]:
        """Keep the dashboard close to v2: first four pneumatic valves plus all fluidic valves."""
        pneumatic_items = [item for item in items if item.get("group") == "pneumatic"]
        fluidic_items = [item for item in items if item.get("group") == "fluidic"]
        other_items = [
            item
            for item in items
            if item.get("group") not in {"pneumatic", "fluidic"}
        ]
        if len(pneumatic_items) <= 4 and not fluidic_items:
            return items
        return pneumatic_items[:4] + fluidic_items + other_items

    def _set_valve(self, valve_name: str, checked: bool, button) -> None:
        """Forward the valve command and roll the UI back if the command was rejected."""
        ok = self.controller.set_valve_state_by_name(valve_name, bool(checked))
        if not ok:
            self._set_button_active(button, False)
            self.controller.append_log(f"[v3] Valve not available: {valve_name}")

    def _apply_status(self, status: dict) -> None:
        """Disable valve commands and mirror the latest known valve states."""
        enabled = bool(status.get("connected"))
        self.close_all.setEnabled(enabled)
        valve_names = list(status.get("valve_names") or [])
        valve_states = list(status.get("valve_states") or [])
        state_by_name = {
            str(name): bool(state)
            for name, state in zip(valve_names, valve_states)
        }
        for button in self._buttons.values():
            button.setEnabled(enabled)
        for valve_name, button in self._buttons.items():
            if valve_name in state_by_name:
                self._set_button_active(button, state_by_name[valve_name])

    @staticmethod
    def _set_button_active(button, active: bool) -> None:
        """Update checked state and dynamic styling for one valve button."""
        button.blockSignals(True)
        button.setChecked(bool(active))
        button.setProperty("valveActive", bool(active))
        if active:
            button.setStyleSheet(
                "QPushButton { background-color: #3b6f78; color: white; border: 1px solid #2b535a; "
                "border-radius: 8px; font-weight: 700; padding: 3px 8px; }"
                "QPushButton:hover { background-color: #467f89; }"
            )
        else:
            button.setStyleSheet("")
        button.blockSignals(False)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()
