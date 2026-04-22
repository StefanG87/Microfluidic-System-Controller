"""Helpers for generating CSV output paths and writing measurement exports."""

import csv
import os
from datetime import datetime


class CSVExporter:
    """Create stable CSV file paths and write measurement CSV files."""

    @staticmethod
    def generate_filename(prefix="Job", folder=None, extension=".csv"):
        """Return a unique file path in the target folder using a timestamped name."""
        if folder is None:
            folder = os.getcwd()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = f"{prefix}_{timestamp}"
        filename = f"{base}{extension}"
        path = os.path.join(folder, filename)

        counter = 1
        while os.path.exists(path):
            filename = f"{base}_{counter}{extension}"
            path = os.path.join(folder, filename)
            counter += 1

        return path

    @staticmethod
    def ensure_measurements_folder():
        """Create and return the default Measurements folder at the project root."""
        base_path = os.path.dirname(os.path.abspath(__file__))
        measurements_folder = os.path.join(os.path.abspath(os.path.join(base_path, "..")), "Measurements")
        os.makedirs(measurements_folder, exist_ok=True)
        return measurements_folder

    @staticmethod
    def _decimal_text(value):
        """Format numeric values with the decimal comma expected by existing exports."""
        return str(value).replace(".", ",")

    @staticmethod
    def _fluigent_header(fluigent_sensors, fluigent_data):
        """Return sensor-specific Fluigent column labels when sensor metadata is available."""
        if fluigent_sensors and len(fluigent_sensors) == len(fluigent_data):
            return [f"SN{sensor.device_sn} [mbar]" for sensor in fluigent_sensors]
        return [f"Pressure {i+1} [mbar]" for i in range(len(fluigent_data))]

    @staticmethod
    def write_measurement_csv(
        path,
        *,
        time_data,
        target,
        corrected,
        measured,
        valve_states,
        flow_data,
        fluigent_data,
        offset=0.0,
        sampling_interval_ms=None,
        start_timestamp=None,
        rotary_active=None,
        valve_names=None,
        profile_name=None,
        valve_coils=None,
        fluigent_sensors=None,
    ):
        """Write one complete measurement export to `path` using the established CSV format."""
        rotary_active = rotary_active or []
        valve_names = list(valve_names) if valve_names else None
        valve_coils = list(valve_coils) if valve_coils else None
        fluigent_sensors = list(fluigent_sensors) if fluigent_sensors else []

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")

            writer.writerow(["Exported", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            writer.writerow(["Offset [mbar]", f"{offset:.2f}".replace(".", ",")])
            writer.writerow(["Sampling interval [ms]", str(sampling_interval_ms)])
            writer.writerow(["Hardware profile", profile_name or "-"])
            if valve_coils and valve_names:
                writer.writerow(["Valve mapping (name -> coil)"])
                for i, name in enumerate(valve_names):
                    coil = valve_coils[i] if i < len(valve_coils) else "-"
                    writer.writerow([f"V{i+1}", name, f"coil {coil}"])

            writer.writerow([])
            if start_timestamp:
                dt = datetime.fromtimestamp(start_timestamp)
                writer.writerow(["Start timestamp (absolute)", dt.strftime("%Y-%m-%d %H:%M:%S")])

            header = ["Absolute Time [ISO]", "Time [s]", "Target [mbar]", "Corrected [mbar]", "Measured [mbar]"]
            if valve_names and len(valve_names) >= 1:
                header += [str(name) for name in valve_names]
            else:
                header += [f"V{i+1}" for i in range(8)]

            header += [f"Flow {i+1} [uL/min]" for i in range(len(flow_data))]
            header += CSVExporter._fluigent_header(fluigent_sensors, fluigent_data)
            header.append("Rotary Active")
            writer.writerow(header)

            for i in range(len(time_data)):
                abs_timestamp = time_data[i]
                rel_time = round(abs_timestamp - start_timestamp, 2) if start_timestamp else 0.0
                abs_time_str = datetime.fromtimestamp(abs_timestamp).strftime("%Y-%m-%d %H:%M:%S")

                row = [
                    abs_time_str,
                    CSVExporter._decimal_text(rel_time),
                    CSVExporter._decimal_text(target[i] if i < len(target) else 0.0),
                    CSVExporter._decimal_text(corrected[i] if i < len(corrected) else 0.0),
                    CSVExporter._decimal_text(measured[i] if i < len(measured) else 0.0),
                ]

                row += [str(v) for v in valve_states[i]] if i < len(valve_states) else ["0"] * 8
                row += [
                    CSVExporter._decimal_text(flow_data[j][i] if i < len(flow_data[j]) else 0.0)
                    for j in range(len(flow_data))
                ]
                row += [
                    CSVExporter._decimal_text(fluigent_data[j][i] if i < len(fluigent_data[j]) else 0.0)
                    for j in range(len(fluigent_data))
                ]

                if rotary_active and i < len(rotary_active):
                    rv = rotary_active[i]
                    row.append(str(int(rv)) if isinstance(rv, int) and rv > 0 else "-")
                else:
                    row.append("-")

                writer.writerow(row)
