"""Helpers for generating CSV output paths and writing measurement exports."""

import csv
import os
import re
from datetime import datetime

from modules.mf_common import writable_app_root


class CSVExporter:
    """Create stable CSV file paths and write measurement CSV files."""

    @staticmethod
    def generate_filename(prefix="Job", folder=None, extension=".csv"):
        """Return a unique file path in the target folder using a timestamped name."""
        if folder is None:
            folder = os.getcwd()

        prefix = CSVExporter.sanitize_prefix(prefix)
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
    def sanitize_prefix(prefix):
        """Return a filesystem-safe export prefix while preserving readable names."""
        text = str(prefix or "").strip() or "measurement"
        text = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE).strip("_")
        return text or "measurement"

    @staticmethod
    def ensure_measurements_folder():
        """Create and return the default Measurements folder for the active runtime."""
        measurements_folder = os.path.join(writable_app_root(), "Measurements")
        os.makedirs(measurements_folder, exist_ok=True)
        return measurements_folder

    @staticmethod
    def _decimal_text(value):
        """Format numeric values with the decimal comma expected by existing exports."""
        return str(value).replace(".", ",")

    @staticmethod
    def _decimal_float(value, decimals=3):
        """Format a numeric value with fixed decimals and decimal comma."""
        if value in ("", None):
            return ""
        try:
            return CSVExporter._decimal_text(f"{float(value):.{int(decimals)}f}")
        except Exception:
            return ""

    @staticmethod
    def _fluigent_header(fluigent_sensors, fluigent_data):
        """Return sensor-specific Fluigent column labels when sensor metadata is available."""
        if fluigent_sensors and len(fluigent_sensors) == len(fluigent_data):
            return [f"SN{sensor.device_sn} [mbar]" for sensor in fluigent_sensors]
        return [f"Pressure {i+1} [mbar]" for i in range(len(fluigent_data))]

    @staticmethod
    def _valve_header(valve_names, valve_states):
        """Return valve column labels from profile metadata or sampled state width."""
        state_width = max((len(row) for row in valve_states or []), default=0)
        if valve_names:
            labels = [str(name) for name in valve_names]
            if state_width > len(labels):
                labels.extend(f"V{i+1}" for i in range(len(labels), state_width))
            return labels
        return [f"V{i+1}" for i in range(state_width)]

    @staticmethod
    def _valve_row_values(valve_states, row_index, valve_column_count):
        """Return one valve-state row padded to the exported valve column count."""
        values = list(valve_states[row_index]) if row_index < len(valve_states) else []
        if len(values) < valve_column_count:
            values.extend(0 for _ in range(valve_column_count - len(values)))
        return [str(value) for value in values[:valve_column_count]]

    @staticmethod
    def _series_attr(series, key, default=None):
        """Read one generic-series field from dict-like or object-like metadata."""
        if isinstance(series, dict):
            return series.get(key, default)
        return getattr(series, key, default)

    @staticmethod
    def _extra_series_header(extra_series):
        """Return CSV labels for generic future measurement channels."""
        labels = []
        for series in extra_series:
            name = str(CSVExporter._series_attr(series, "name", "")).strip()
            unit = str(CSVExporter._series_attr(series, "unit", "") or "").strip()
            if not name:
                continue
            labels.append(f"{name} [{unit}]" if unit else name)
        return labels

    @staticmethod
    def _extra_series_values(series):
        """Return generic-series values as a list."""
        values = CSVExporter._series_attr(series, "values", [])
        return list(values) if values is not None else []

    @staticmethod
    def _timing_attr(timing, key, default=None):
        """Read one timing field from dict-like or object-like metadata."""
        if isinstance(timing, dict):
            return timing.get(key, default)
        return getattr(timing, key, default)

    @staticmethod
    def _timing_channels(read_timing_data):
        """Return timing-channel labels in first-seen order."""
        channels = []
        seen = set()
        for sample in read_timing_data or []:
            for timing in sample or []:
                channel = str(CSVExporter._timing_attr(timing, "channel", "")).strip()
                if channel and channel not in seen:
                    seen.add(channel)
                    channels.append(channel)
        return channels

    @staticmethod
    def _timing_by_channel(sample_timing):
        """Return one timing row indexed by channel label."""
        indexed = {}
        for timing in sample_timing or []:
            channel = str(CSVExporter._timing_attr(timing, "channel", "")).strip()
            if channel:
                indexed[channel] = timing
        return indexed

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
        extra_series=None,
        include_read_timing=False,
        sample_finished_time_data=None,
        read_timing_data=None,
        configured_interval_data=None,
    ):
        """Write one complete measurement export to `path` using the established CSV format."""
        rotary_active = rotary_active or []
        valve_names = list(valve_names) if valve_names else None
        valve_coils = list(valve_coils) if valve_coils else None
        fluigent_sensors = list(fluigent_sensors) if fluigent_sensors else []
        extra_series = [
            series
            for series in (list(extra_series) if extra_series else [])
            if str(CSVExporter._series_attr(series, "name", "")).strip()
        ]
        sample_finished_time_data = list(sample_finished_time_data) if sample_finished_time_data else []
        read_timing_data = list(read_timing_data) if read_timing_data else []
        configured_interval_data = list(configured_interval_data) if configured_interval_data else []
        timing_channels = CSVExporter._timing_channels(read_timing_data) if include_read_timing else []

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")

            writer.writerow(["Exported", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            writer.writerow(["Offset [mbar]", f"{offset:.2f}".replace(".", ",")])
            writer.writerow(["Sampling interval [ms]", str(sampling_interval_ms)])
            writer.writerow(["Hardware profile", profile_name or "-"])
            if include_read_timing:
                writer.writerow(["Detailed read timing", "enabled"])
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
            if include_read_timing:
                header += [
                    "Configured Interval [ms]",
                    "Actual Sample Period [ms]",
                    "Sample Start Epoch [s]",
                    "Sample Finished Epoch [s]",
                    "Sample Duration [ms]",
                ]
                for channel in timing_channels:
                    header += [
                        f"{channel} read start offset [ms]",
                        f"{channel} read duration [ms]",
                    ]
            valve_header = CSVExporter._valve_header(valve_names, valve_states)
            header += valve_header

            header += [f"Flow {i+1} [uL/min]" for i in range(len(flow_data))]
            header += CSVExporter._fluigent_header(fluigent_sensors, fluigent_data)
            header += CSVExporter._extra_series_header(extra_series)
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

                if include_read_timing:
                    sample_finished = sample_finished_time_data[i] if i < len(sample_finished_time_data) else None
                    configured_interval = (
                        configured_interval_data[i]
                        if i < len(configured_interval_data) and configured_interval_data[i] is not None
                        else sampling_interval_ms
                    )
                    actual_period_ms = (
                        (float(time_data[i]) - float(time_data[i - 1])) * 1000.0
                        if i > 0 and i < len(time_data)
                        else None
                    )
                    row += [
                        str(configured_interval) if configured_interval is not None else "",
                        CSVExporter._decimal_float(actual_period_ms, decimals=3),
                        CSVExporter._decimal_float(abs_timestamp, decimals=6),
                        CSVExporter._decimal_float(sample_finished, decimals=6),
                        CSVExporter._decimal_float(
                            (float(sample_finished) - float(abs_timestamp)) * 1000.0
                            if sample_finished is not None
                            else None,
                            decimals=3,
                        ),
                    ]
                    timing_by_channel = CSVExporter._timing_by_channel(
                        read_timing_data[i] if i < len(read_timing_data) else []
                    )
                    for channel in timing_channels:
                        timing = timing_by_channel.get(channel)
                        started = CSVExporter._timing_attr(timing, "started_abs") if timing is not None else None
                        finished = CSVExporter._timing_attr(timing, "finished_abs") if timing is not None else None
                        row += [
                            CSVExporter._decimal_float(
                                (float(started) - float(abs_timestamp)) * 1000.0
                                if started is not None
                                else None,
                                decimals=3,
                            ),
                            CSVExporter._decimal_float(
                                (float(finished) - float(started)) * 1000.0
                                if started is not None and finished is not None
                                else None,
                                decimals=3,
                            ),
                        ]

                row += CSVExporter._valve_row_values(valve_states, i, len(valve_header))
                row += [
                    CSVExporter._decimal_text(flow_data[j][i] if i < len(flow_data[j]) else 0.0)
                    for j in range(len(flow_data))
                ]
                row += [
                    CSVExporter._decimal_text(fluigent_data[j][i] if i < len(fluigent_data[j]) else 0.0)
                    for j in range(len(fluigent_data))
                ]
                for series in extra_series:
                    values = CSVExporter._extra_series_values(series)
                    value = values[i] if i < len(values) else ""
                    row.append(CSVExporter._decimal_text(value) if value not in ("", None) else "")

                if rotary_active and i < len(rotary_active):
                    rv = rotary_active[i]
                    row.append(str(int(rv)) if isinstance(rv, int) and rv > 0 else "-")
                else:
                    row.append("-")

                writer.writerow(row)
