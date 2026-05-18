"""Balance connection card for the v3 hardware settings page."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox, QWidget

from modules.mf_common import load_last_comport
from modules.rvm_dt import list_serial_ports
from ui_v3.fluent_compat import CardWidget, PushButton, add_info_header, make_card_layout


class BalanceConnectionCard(CardWidget):
    """Connect and monitor an optional Ohaus-compatible serial balance."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        layout = make_card_layout(self)
        add_info_header(
            layout,
            "Balance Connection",
            "Connects an Ohaus-compatible balance as an optional live measurement channel. "
            "Use 9600 baud, 8N1, no flow control, unit g, and auto-print at about 1 s according to the SOP.",
        )

        self.status = QLabel("Status: -")
        self.mass = QLabel("Mass: -")
        self.com = QComboBox()
        self.refresh_button = PushButton("Refresh Ports")
        self.connect_button = PushButton("Connect Balance")
        self.disconnect_button = PushButton("Disconnect")
        self.read_button = PushButton("Read Once")

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        row_layout.addWidget(QLabel("COM:"))
        row_layout.addWidget(self.com, 1)
        row_layout.addWidget(self.refresh_button)
        row_layout.addWidget(self.connect_button)
        row_layout.addWidget(self.disconnect_button)
        row_layout.addWidget(self.read_button)

        layout.addWidget(self.status)
        layout.addWidget(self.mass)
        layout.addWidget(row)

        self.refresh_button.clicked.connect(lambda _checked=False: self.refresh_ports())
        self.connect_button.clicked.connect(lambda _checked=False: self.connect_balance())
        self.disconnect_button.clicked.connect(lambda _checked=False: self.controller.disconnect_balance())
        self.read_button.clicked.connect(lambda _checked=False: self.read_once())
        self.controller.status_changed.connect(self._sync_status)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self.read_once)
        self.refresh_ports()
        self._sync_status(self.controller.status_snapshot())

    def refresh_ports(self) -> None:
        """Refresh COM ports and preselect the saved balance port."""
        current = self.com.currentText().strip()
        self.com.clear()
        for port in list_serial_ports():
            self.com.addItem(port)
        preferred = current or load_last_comport("balance") or ""
        if preferred:
            index = self.com.findText(preferred)
            if index < 0:
                self.com.addItem(preferred)
                index = self.com.findText(preferred)
            if index >= 0:
                self.com.setCurrentIndex(index)

    def connect_balance(self) -> None:
        """Connect the selected balance port through the runtime controller."""
        port = self.com.currentText().strip()
        if not port:
            QMessageBox.information(self, "Balance", "Please choose a COM port.")
            return
        if self.controller.connect_balance(port):
            self.poll_timer.start()

    def read_once(self) -> None:
        """Update the displayed mass from the connected balance."""
        mass = self.controller.read_balance_mass_g(timeout_s=0.2)
        if mass is not None:
            self.mass.setText(f"Mass: {mass:.5f} g")
        self._sync_status(self.controller.status_snapshot())

    def _sync_status(self, status: dict) -> None:
        """Reflect current balance state in the settings card."""
        connected = bool(status.get("balance_connected"))
        port = str(status.get("balance_port") or self.com.currentText().strip() or "-")
        self.status.setText(f"Status: {'connected' if connected else 'disconnected'} | COM: {port}")
        mass = status.get("balance_mass_g")
        if mass is not None:
            self.mass.setText(f"Mass: {float(mass):.5f} g")
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        self.read_button.setEnabled(connected)
        if not connected:
            self.poll_timer.stop()
