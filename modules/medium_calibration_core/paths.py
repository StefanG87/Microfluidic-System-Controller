"""Path helpers shared by the calibration core."""

from __future__ import annotations

from pathlib import Path

from modules.mf_common import resource_path, writable_app_root


PROJECT_ROOT = Path(writable_app_root())
LOOKUP_DIR = Path(resource_path("lookup"))
DEFAULT_DENSITY_LOOKUP = LOOKUP_DIR / "EtOH_density_20C.json"
DEFAULT_PRESSURE_OFFSET = LOOKUP_DIR / "pressure_offset.json"
DEFAULT_CALIBRATION_DIR = PROJECT_ROOT / "calibration_EtOH"
DEFAULT_FLOW_CORRECTION_FILE = LOOKUP_DIR / "flow_correction_etoh.json"
