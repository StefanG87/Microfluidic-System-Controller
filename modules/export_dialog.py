"""Dialog for exporting measurement buffers to CSV."""

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox, QPushButton, QVBoxLayout

from modules.csv_exporter import CSVExporter
from modules.measurement_session import ExportSnapshot


class ExportDialog(QDialog):
    """Export pressure, flow, valve, and rotary data from the current session."""

    def __init__(
        self,
        parent,
        time_data=None,
        target=None,
        corrected=None,
        measured=None,
        valve_states=None,
        flow_data=None,
        fluigent_data=None,
        offset=0.0,
        sampling_interval_ms=None,
        start_timestamp=None,
        auto_path=None,
        silent=False,
        rotary_active=None,
        valve_names=None,
        profile_name=None,
        valve_coils=None,
        sampling_rate=None,
        snapshot: ExportSnapshot | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("CSV Export")
        layout = QVBoxLayout(self)

        self.auto_path = auto_path
        self._final_path = auto_path
        self.silent = silent
        if snapshot is not None:
            time_data = snapshot.time_data
            target = snapshot.target_data
            corrected = snapshot.corrected_data
            measured = snapshot.measured_data
            valve_states = snapshot.valve_states
            flow_data = snapshot.flow_data
            fluigent_data = snapshot.fluigent_data
            offset = snapshot.offset
            sampling_interval_ms = snapshot.sampling_interval_ms
            start_timestamp = snapshot.start_timestamp
            rotary_active = snapshot.rotary_active
            valve_names = snapshot.valve_names
            profile_name = snapshot.profile_name
            valve_coils = snapshot.valve_coils
            extra_series = snapshot.extra_series or []
        else:
            extra_series = []

        self.time_data = time_data or []
        self.target = target or []
        self.corrected = corrected or []
        self.measured = measured or []
        self.valve_states = valve_states or []
        self.flow_data = flow_data or []
        self.fluigent_data = fluigent_data or []
        self.offset = offset
        if sampling_interval_ms is None:
            sampling_interval_ms = sampling_rate
        self.sampling_interval_ms = sampling_interval_ms
        self.sampling_rate = sampling_interval_ms  # Legacy alias for older export callers.
        self.start_timestamp = start_timestamp
        self.rotary_active = rotary_active or []
        self.valve_names = list(valve_names) if valve_names else None
        self.profile_name = str(profile_name) if profile_name else None
        self.valve_coils = list(valve_coils) if valve_coils else None
        self.fluigent_sensors = parent.fluigent_sensors if hasattr(parent, "fluigent_sensors") else []
        self.extra_series = extra_series

        btn = QPushButton("Save CSV")
        btn.clicked.connect(self.save_csv)
        layout.addWidget(btn)

        if self.auto_path:
            QTimer.singleShot(0, lambda: self.save_csv(path=self.auto_path, silent=self.silent))
            QTimer.singleShot(50, self.accept)

    def save_csv(self, path=None, silent=False):
        """Write the buffered measurement data to the selected CSV path."""
        path = path or getattr(self, "_final_path", None)

        if path is None:
            folder = CSVExporter.ensure_measurements_folder()
            default_path = CSVExporter.generate_filename(prefix="measurement", folder=folder)

            if not silent and self.isVisible():
                suggested_name = str(default_path)
                path, _ = QFileDialog.getSaveFileName(
                    self, "Save CSV", suggested_name, "CSV (*.csv)"
                )
                if not path:
                    return
            else:
                path = str(default_path)

        self._final_path = path

        try:
            CSVExporter.write_measurement_csv(
                path,
                time_data=self.time_data,
                target=self.target,
                corrected=self.corrected,
                measured=self.measured,
                valve_states=self.valve_states,
                flow_data=self.flow_data,
                fluigent_data=self.fluigent_data,
                offset=self.offset,
                sampling_interval_ms=self.sampling_interval_ms,
                start_timestamp=self.start_timestamp,
                rotary_active=self.rotary_active,
                valve_names=self.valve_names,
                profile_name=self.profile_name,
                valve_coils=self.valve_coils,
                fluigent_sensors=self.fluigent_sensors,
                extra_series=self.extra_series,
            )

            if not silent and self.isVisible():
                QMessageBox.information(self, "Success", f"Data saved to:\n{path}")

            self.close()

        except Exception as e:
            if not silent and self.isVisible():
                QMessageBox.critical(self, "Export error", str(e))
            else:
                print(f"[Export error] {e}")
