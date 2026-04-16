"""Helpers for generating CSV output paths and default folders."""

import os
from datetime import datetime


class CSVExporter:
    """Create stable CSV file paths for manual and automated exports."""

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
    def save_csv(data, folder, filename):
        """
        Legacy placeholder kept for compatibility with older call sites.
        Real measurement exports are handled by the GUI export workflow.
        """
        filepath = os.path.join(folder, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("Example,Data,Here\n")
        print(f"[CSVExporter] Legacy placeholder save_csv() wrote: {filepath}")
