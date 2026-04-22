from __future__ import annotations
from typing import Iterable, Optional
import json
import os
import sys
import tempfile

try:
    from PyQt5.QtWidgets import QMessageBox, QInputDialog, QWidget
except Exception:  # headless or non-Qt contexts
    QMessageBox = None
    QInputDialog = None
    QWidget = object  # type: ignore


def _source_root() -> str:
    """Return the source-tree root that contains the modules and lookup folders."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def resource_path(relative_path: str) -> str:
    """Resolve a resource path for source runs and PyInstaller bundles."""
    base_path = getattr(sys, "_MEIPASS", None) or _source_root()
    return os.path.join(base_path, relative_path)


def _lookup_dir() -> str:
    """Resolve the lookup folder for source runs and bundled deployments."""
    candidates = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "lookup"))
        candidates.append(os.path.join(os.path.abspath(os.path.join(meipass, "..")), "lookup"))

    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "lookup"))

    candidates.append(os.path.join(os.path.abspath("."), "lookup"))
    candidates.append(os.path.join(_source_root(), "lookup"))

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate

    return os.path.join(_source_root(), "lookup")


LOOKUP_DIR = _lookup_dir()


# ---------- Error / info logging ----------

def log_error(message: str, display_ui: bool = True, parent: Optional["QWidget"] = None) -> None:
    print(f"[Error] {message}")
    if display_ui and QMessageBox:
        QMessageBox.critical(parent, "Error", message)

def log_info(message: str, display_ui: bool = False, parent: Optional["QWidget"] = None) -> None:
    print(f"[Info] {message}")
    if display_ui and QMessageBox:
        QMessageBox.information(parent, "Info", message)


# ---------- Small UI helpers ----------

def select_item(parent: Optional["QWidget"], title: str, label: str, items: Iterable[str]) -> Optional[str]:
    """Generic single-choice selector via QInputDialog."""
    if not QInputDialog:
        return None
    items = list(items)
    if not items:
        if QMessageBox:
            QMessageBox.warning(parent, title, "No items available.")
        return None
    choice, ok = QInputDialog.getItem(parent, title, label, items, 0, False)
    return choice if ok else None


# ---------- Valve helpers (avoid duplicate toggle code) ----------

def toggle_coil(bus, address: int, current_state: int) -> int:
    """
    Toggles a Modbus coil (0/1) and returns the new state.
    Expects `bus.write_coil(address, value)` to be available.
    """
    new_state = 0 if current_state else 1
    bus.write_coil(address, new_state)
    return new_state

# ---------- offset store ----------

DEFAULT_OFFSET_PATH = os.path.join(LOOKUP_DIR, "pressure_offset.json")

def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

def load_pressure_offset(path: str = DEFAULT_OFFSET_PATH) -> float:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # allow future schema like {"offset": ..., "unit": "mbar", "ts": "..."}
                return float(data.get("offset", 0.0))
    except Exception as e:
        print(f"[Offset] Load failed ({path}): {e}")
    return 0.0



def save_pressure_offset(offset_mbar: float, path: str = DEFAULT_OFFSET_PATH) -> bool:
    try:
        _ensure_dir(path)
        d = {"offset": float(offset_mbar)}
        # write to temp, then replace
        dir_ = os.path.dirname(os.path.abspath(path))
        with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_, encoding="utf-8") as tmp:
            json.dump(d, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = tmp.name
        os.replace(tmp_path, path)
        print(f"[Offset] Saved {offset_mbar:.3f} mbar -> {path}")
        return True
    except Exception as e:
        print(f"[Offset] Save failed ({path}): {e}")
        return False

# ---------- device prefs (e.g., rotary valve last COM) ----------

from datetime import datetime

DEFAULT_PREFS_PATH = os.path.join(LOOKUP_DIR, "device_prefs.json")

def _atomic_save_json(data: dict, path: str) -> bool:
    try:
        _ensure_dir(path)
        dir_ = os.path.dirname(os.path.abspath(path))
        with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_, encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = tmp.name
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        print(f"[Prefs] Save failed ({path}): {e}")
        return False

def _load_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Prefs] Load failed ({path}): {e}")
    return {}

def load_last_comport(device_key: str = "rotary_valve",
                      path: str = DEFAULT_PREFS_PATH) -> Optional[str]:
    """
    Returns last stored COM port for the given device key, e.g. 'COM8',
    or None if not stored.
    JSON shape:
    {
      "rotary_valve": {"last_comport": "COM8", "ts": "..."},
      ...
    }
    """
    data = _load_json(path)
    dev = data.get(device_key, {})
    port = dev.get("last_comport")
    return str(port) if port else None

def save_last_comport(port: str,
                      device_key: str = "rotary_valve",
                      path: str = DEFAULT_PREFS_PATH) -> bool:
    """
    Stores last COM port for given device key.
    """
    data = _load_json(path)
    if device_key not in data:
        data[device_key] = {}
    data[device_key]["last_comport"] = str(port)
    data[device_key]["ts"] = datetime.utcnow().isoformat() + "Z"
    ok = _atomic_save_json(data, path)
    if ok:
        print(f"[Prefs] {device_key}: last_comport = {port} -> {path}")
    return ok

# ---------- hardware profile preference in device_prefs.json ----------

def load_hw_profile_from_prefs(default: str = "stand1",
                               path: str = DEFAULT_PREFS_PATH) -> str:
    """
    Reads the last used hardware profile (e.g., 'stand1' / 'stand2')
    from lookup/device_prefs.json. Falls back to the default if no value is stored.
    """
    data = _load_json(path)
    dev = data.get("hardware", {})
    name = dev.get("hw_profile")
    return str(name) if name else default


def save_hw_profile_to_prefs(name: str,
                             path: str = DEFAULT_PREFS_PATH) -> bool:
    """
    Stores the last used hardware profile in lookup/device_prefs.json.
    JSON schema:
    {
      "hardware": {"hw_profile": "stand2", "ts": "..."},
      "rotary_valve": {...}
    }
    """
    data = _load_json(path)
    if "hardware" not in data:
        data["hardware"] = {}
    data["hardware"]["hw_profile"] = str(name)
    data["hardware"]["ts"] = datetime.utcnow().isoformat() + "Z"
    ok = _atomic_save_json(data, path)
    if ok:
        print(f"[Prefs] hardware.hw_profile = {name} -> {path}")
    return ok


def list_system_serial_ports() -> list:
    """
    Return the available serial port names as strings.
    This helper is currently unused by the application code.
    """
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except Exception:
        return []

def _settings_json_path() -> str:
    """
    Central app settings file (shared with other small prefs).
    Adjust path if you already have a global settings file.
    """
    base = os.path.join(os.path.expanduser("~"), ".mf_controller")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "settings.json")

def load_last_modbus_ip() -> Optional[str]:
    try:
        path = _settings_json_path()
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("last_modbus_ip")
    except Exception:
        pass
    return None

def save_last_modbus_ip(ip: str) -> bool:
    try:
        path = _settings_json_path()
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["last_modbus_ip"] = ip
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False
    
# ---------- hardware profile (valve mapping & labels) ----------


def _default_profile_stand1() -> dict:
    """
    Default mapping for stand 1.
    Keep the valve order aligned with the GUI valve list and editor valve names.
    """
    items = []
    # Pneumatic 1..4 -> coils 0..3
    for i in range(4):
        items.append({
            "group": "pneumatic",
            "coil": i,
            "editor_name": f"Pneumatic {i+1}",
            "button_label": f"Valve {i+1}",
        })
    # Fluidic 5..8 -> coils 4..7
    for i in range(4):
        num = i + 5  # 5..8
        coil = i + 4 # 4..7
        items.append({
            "group": "fluidic",
            "coil": coil,
            "editor_name": f"Fluidic {num}",
            "button_label": f"Valve {num}",
        })
    return {
        "name": "stand1",
        "valve_groups": [
            {"box": "Pneumatic Valves", "items": items[0:4]},
            {"box": "Fluidic Valves",   "items": items[4:8]},
        ],
    }

def _default_profile_stand2() -> dict:
    """
    Default mapping for stand 2.
    The coil indices are placeholders and should be overridden by a profile file when available.
    """
    pneu = [{
        "group": "pneumatic",
        "coil": i,  # temporary mapping
        "editor_name": f"Pneumatic {i+1}",
        "button_label": f"Valve {i+1}",
    } for i in range(4)]
    flu = [{
        "group": "fluidic",
        "coil": i + 4,  # temporary mapping
        "editor_name": f"Fluidic {i+1}",
        "button_label": f"Valve {i+1}",
    } for i in range(4)]
    return {
        "name": "stand2",
        "valve_groups": [
            {"box": "Pneumatic Valves", "items": pneu},
            {"box": "Fluidic Valves",   "items": flu},
        ],
    }


# ---------- hardware profiles in lookup/ ----------

def load_hardware_profile(name_or_path: str = None) -> dict:
    """
    Load a hardware profile from lookup/<name>.json or from an explicit file path.
    Fall back to the built-in stand1/stand2 defaults if no valid file is found.
    """
    import os, json

    # 1) Explicit file path
    if name_or_path and os.path.isfile(name_or_path):
        try:
            with open(name_or_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "valve_groups" in data:
                return data
        except Exception as e:
            print(f"[Profile] Load failed ({name_or_path}): {e}")
    # 2) Profile name -> lookup/<name>.json (default: stand1)
    name = (name_or_path or os.environ.get("MF_HW_PROFILE", "stand1")).lower()
    candidate = os.path.join(LOOKUP_DIR, f"{name}.json")
    try:
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "valve_groups" in data:
                return data
    except Exception as e:
        print(f"[Profile] Load failed ({candidate}): {e}")

    # 3) Fallback defaults
    if name == "stand2":
        return _default_profile_stand2()
    return _default_profile_stand1()


def list_hw_profiles(dirpath: Optional[str] = None) -> list[str]:
    """
    Return profile names for JSON files in the lookup folder that define valve_groups.
    """
    import os, json
    dirpath = dirpath or LOOKUP_DIR
    out = []
    try:
        for fn in os.listdir(dirpath):
            if not fn.lower().endswith(".json"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "valve_groups" in data:
                    out.append(os.path.splitext(fn)[0])
            except Exception:
                continue
    except Exception:
        pass
    # Sort profile names deterministically (stand1 before stand2, and so on).
    out.sort()
    return out


