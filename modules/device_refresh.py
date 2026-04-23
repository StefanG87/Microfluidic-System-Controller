"""User-facing status helpers for manual hardware configuration refreshes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def empty_rotary_refresh_status(
    *,
    connected=False,
    reachable=None,
    device_status="",
    error="",
) -> dict:
    """Return the default status shape used for rotary refresh reporting."""
    return {
        "ports_added": [],
        "ports_removed": [],
        "connected": bool(connected),
        "reachable": reachable,
        "device_status": str(device_status or ""),
        "error": str(error or ""),
    }


def probe_pressure_monitor(read_pressure_mbar) -> bool:
    """Check whether the internal pressure monitor can be read without changing outputs."""
    return read_pressure_mbar() is not None


def probe_configured_flow_inputs(flow_sensors) -> dict:
    """Check configured analog flow inputs; this verifies Modbus readability, not physical sensor identity."""
    readable = []
    failed = []
    for sensor in flow_sensors or []:
        name = getattr(sensor, "name", "Flow")
        if sensor.read_flow() is None:
            failed.append(name)
        else:
            readable.append(name)
    return {"readable": readable, "failed": failed}


def refresh_rotary_config_status(rotary_box) -> dict:
    """Refresh rotary COM-port discovery and return a conservative communication status."""
    if rotary_box is None:
        return empty_rotary_refresh_status(error="rotary widget unavailable")

    if hasattr(rotary_box, "refresh_config_status"):
        return rotary_box.refresh_config_status()

    try:
        rotary_box._refresh()
        return empty_rotary_refresh_status(connected=bool(rotary_box.ctl.is_connected()))
    except Exception as e:
        return empty_rotary_refresh_status(reachable=False, error=str(e))


def refresh_fluigent_sensor_list(current_sensors, detect_sensors):
    """Run a fresh Fluigent scan while preserving software zero offsets by serial number."""
    previous_offsets = {
        str(getattr(sensor, "device_sn", "")): getattr(sensor, "offset", 0.0)
        for sensor in current_sensors or []
        if str(getattr(sensor, "device_sn", ""))
    }

    refreshed_sensors = detect_sensors(force_reinit=True)
    for sensor in refreshed_sensors:
        sensor_key = str(getattr(sensor, "device_sn", ""))
        if sensor_key in previous_offsets:
            sensor.offset = previous_offsets[sensor_key]
    return refreshed_sensors


def summarize_device_config_refresh(
    *,
    old_sensors,
    new_sensors,
    old_actuators,
    new_actuators,
    pressure_readable,
    flow_status,
    rotary_status,
) -> str:
    """Build a concise user-facing summary for one manual device refresh."""
    details = []
    details.extend(_format_catalog_changes("sensors", old_sensors, new_sensors))
    details.extend(_format_catalog_changes("actuators", old_actuators, new_actuators))

    if not details:
        details.append("no catalog changes")

    details.append(
        "pressure monitor register readable"
        if pressure_readable
        else "pressure monitor register read failed"
    )
    details.extend(_format_flow_status(flow_status))
    details.extend(_format_rotary_status(rotary_status))
    return "; ".join(details)


def _format_catalog_changes(label, before, after):
    """Return short summary fragments for added or removed catalog entries."""
    added = sorted(set(_display_values(after)) - set(_display_values(before)))
    removed = sorted(set(_display_values(before)) - set(_display_values(after)))
    details = []
    if added:
        details.append(f"{label} added: {', '.join(added)}")
    if removed:
        details.append(f"{label} removed: {', '.join(removed)}")
    return details


def _format_flow_status(flow_status):
    """Format Modbus-backed flow input readability without implying physical detection."""
    failed = _mapping_list(flow_status, "failed")
    readable = _mapping_list(flow_status, "readable")
    if failed:
        return [f"flow input register read failed: {', '.join(failed)}"]
    if readable:
        return ["flow input registers readable"]
    return ["no flow inputs configured"]


def _format_rotary_status(rotary_status):
    """Format rotary COM-port discovery and communication reachability."""
    ports_added = _mapping_list(rotary_status, "ports_added")
    ports_removed = _mapping_list(rotary_status, "ports_removed")
    details = []

    if ports_added:
        details.append(f"rotary COM ports added: {', '.join(ports_added)}")
    if ports_removed:
        details.append(f"rotary COM ports removed: {', '.join(ports_removed)}")
    if not ports_added and not ports_removed:
        details.append("rotary COM ports unchanged")

    if bool(_mapping_get(rotary_status, "connected", False)):
        reachable = _mapping_get(rotary_status, "reachable", None)
        if reachable is True:
            status_text = _mapping_get(rotary_status, "device_status", "") or "responding"
            details.append(f"rotary reachable: {status_text}")
        elif reachable is False:
            error = _short_status_error(_mapping_get(rotary_status, "error", ""))
            details.append(f"rotary not responding: {error}")
        else:
            details.append("rotary connected")
    else:
        details.append("rotary not connected")

    return details


def _mapping_get(value, key, default=None):
    """Read one status value from mapping-like objects."""
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _mapping_list(value, key):
    """Return one status field as a sorted list of strings."""
    raw = _mapping_get(value, key, [])
    return sorted(_display_values(raw))


def _display_values(value) -> list[str]:
    """Normalize iterable catalog/status values to displayable strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Iterable):
        return [str(value)]
    return [str(item) for item in value]


def _short_status_error(error_text):
    """Keep hardware error details readable inside the config-refresh message box."""
    text = str(error_text or "").strip()
    if len(text) > 90:
        return text[:87] + "..."
    return text or "unknown error"
