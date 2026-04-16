"""Shared editor device catalogs.

These module-level lists are intentionally mutable so importers that bind
`AVAILABLE_SENSORS` / `AVAILABLE_VALVES` once can still observe later updates.
"""

AVAILABLE_SENSORS = []
AVAILABLE_VALVES = []


def update_available_sensors(sensor_list):
    """Replace the published sensor list in place to keep imported aliases fresh."""
    AVAILABLE_SENSORS.clear()
    AVAILABLE_SENSORS.extend(str(sensor) for sensor in sensor_list)


def update_available_valves(valve_list):
    """Replace the published valve list in place to keep imported aliases fresh."""
    AVAILABLE_VALVES.clear()
    AVAILABLE_VALVES.extend(str(valve) for valve in valve_list)


def get_available_sensors():
    """Return the configured sensors or a small fallback set for standalone use."""
    return list(AVAILABLE_SENSORS) or ["Internal", "Flow 1", "SN12345"]


def get_available_valves():
    """Return the configured valves or a small fallback set for standalone use."""
    return list(AVAILABLE_VALVES) or ["Pneumatic 1", "Fluidic 8"]
