"""Dialog and writer for exporting measurement buffers to CSV."""

import csv
from datetime import datetime

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
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")

                writer.writerow(["Exported", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(["Offset [mbar]", f"{self.offset:.2f}".replace(".", ",")])
                writer.writerow(["Sampling interval [ms]", str(self.sampling_interval_ms)])
                writer.writerow(["Hardware profile", self.profile_name or "-"])
                if self.valve_coils and self.valve_names:
                    writer.writerow(["Valve mapping (name -> coil)"])
                    for i, name in enumerate(self.valve_names):
                        coil = self.valve_coils[i] if i < len(self.valve_coils) else "-"
                        writer.writerow([f"V{i+1}", name, f"coil {coil}"])

                writer.writerow([])
                if self.start_timestamp:
                    dt = datetime.fromtimestamp(self.start_timestamp)
                    writer.writerow(["Start timestamp (absolute)", dt.strftime("%Y-%m-%d %H:%M:%S")])

                header = ["Absolute Time [ISO]", "Time [s]", "Target [mbar]", "Corrected [mbar]", "Measured [mbar]"]
                if self.valve_names and len(self.valve_names) >= 1:
                    header += [str(name) for name in self.valve_names]
                else:
                    header += [f"V{i+1}" for i in range(8)]

                header += [f"Flow {i+1} [uL/min]" for i in range(len(self.flow_data))]
                if self.fluigent_sensors and len(self.fluigent_sensors) == len(self.fluigent_data):
                    header += [f"SN{sensor.device_sn} [mbar]" for sensor in self.fluigent_sensors]
                else:
                    header += [f"Pressure {i+1} [mbar]" for i in range(len(self.fluigent_data))]

                header.append("Rotary Active")
                writer.writerow(header)

                for i in range(len(self.time_data)):
                    abs_timestamp = self.time_data[i]
                    rel_time = round(abs_timestamp - self.start_timestamp, 2) if self.start_timestamp else 0.0
                    abs_time_str = datetime.fromtimestamp(abs_timestamp).strftime("%Y-%m-%d %H:%M:%S")

                    row = [
                        abs_time_str,
                        str(rel_time).replace(".", ","),
                        str(self.target[i] if i < len(self.target) else 0.0).replace(".", ","),
                        str(self.corrected[i] if i < len(self.corrected) else 0.0).replace(".", ","),
                        str(self.measured[i] if i < len(self.measured) else 0.0).replace(".", ","),
                    ]

                    row += [str(v) for v in self.valve_states[i]] if i < len(self.valve_states) else ["0"] * 8
                    row += [
                        str(self.flow_data[j][i] if i < len(self.flow_data[j]) else 0.0).replace(".", ",")
                        for j in range(len(self.flow_data))
                    ]
                    row += [
                        str(self.fluigent_data[j][i] if i < len(self.fluigent_data[j]) else 0.0).replace(".", ",")
                        for j in range(len(self.fluigent_data))
                    ]

                    if self.rotary_active and i < len(self.rotary_active):
                        rv = self.rotary_active[i]
                        row.append(str(int(rv)) if isinstance(rv, int) and rv > 0 else "-")
                    else:
                        row.append("-")

                    writer.writerow(row)

            if not silent and self.isVisible():
                QMessageBox.information(self, "Success", f"Data saved to:\n{path}")

            self.close()

        except Exception as e:
            if not silent and self.isVisible():
                QMessageBox.critical(self, "Export error", str(e))
            else:
                print(f"[Export error] {e}")