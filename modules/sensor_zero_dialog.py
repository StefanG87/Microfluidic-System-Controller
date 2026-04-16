"""Dialog for choosing which Fluigent sensors should be zeroed."""

from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SensorZeroDialog(QDialog):
    """Present the available sensors as a selectable checklist."""

    def __init__(self, sensor_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Sensors to Zero")
        self.resize(400, 300)
        self.selected_sensors = []

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.select_all_cb = QCheckBox("Select all")
        self.select_all_cb.stateChanged.connect(self.toggle_all)
        layout.addWidget(self.select_all_cb)

        self.checkboxes = []
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        for sensor in sensor_list:
            label = f"Sensor SN {sensor.device_sn} (Index {sensor.index})"
            cb = QCheckBox(label)
            cb.sensor = sensor
            scroll_layout.addWidget(cb)
            self.checkboxes.append(cb)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def toggle_all(self, state):
        for cb in self.checkboxes:
            cb.setChecked(bool(state))

    def accept_selection(self):
        self.selected_sensors = [cb.sensor for cb in self.checkboxes if cb.isChecked()]
        self.accept()