"""Helpers for Fluigent pressure sensor discovery and readout."""

FLUIGENT_SDK_AVAILABLE = True
FLUIGENT_SDK_IMPORT_ERROR = None

try:
    from Fluigent.SDK import (
        fgt_close,
        fgt_get_sensorChannelsInfo,
        fgt_get_sensorValue,
        fgt_init,
    )
except ImportError:
    try:
        from .Fluigent.SDK import (
            fgt_close,
            fgt_get_sensorChannelsInfo,
            fgt_get_sensorValue,
            fgt_init,
        )
    except ImportError as e:
        FLUIGENT_SDK_AVAILABLE = False
        FLUIGENT_SDK_IMPORT_ERROR = e
        fgt_close = None
        fgt_get_sensorChannelsInfo = None
        fgt_get_sensorValue = None
        fgt_init = None


class FluigentPressureSensor:
    """Lightweight wrapper around one Fluigent sensor channel."""

    def __init__(self, index, device_sn):
        self.index = index
        self.device_sn = device_sn
        self.offset = 0.0

    def read_pressure(self):
        """Read the current pressure and apply the software zero offset."""
        if not FLUIGENT_SDK_AVAILABLE or fgt_get_sensorValue is None:
            return None

        error_code = fgt_get_sensorValue(self.index)
        if error_code is None:
            print(f"[Fluigent] Error reading sensor {self.device_sn} (index: {self.index})")
            return None
        return round(error_code - self.offset, 2)

    def set_zero(self):
        """Store the current reading as a software zero offset."""
        current = self.read_pressure()
        if current is not None:
            self.offset = current
            print(f"[Fluigent] Sensor {self.device_sn} zeroed (software). Offset: {self.offset:.2f} mbar")


def _close_fluigent_sdk():
    """Close the Fluigent SDK connection when a fresh device scan is required."""
    if fgt_close is None:
        return

    try:
        fgt_close()
    except Exception as e:
        print(f"[Fluigent] Failed to close SDK before refresh: {e}")


def detect_fluigent_sensors(force_reinit=False):
    """Initialize the Fluigent SDK and return the detected pressure sensors."""
    if not FLUIGENT_SDK_AVAILABLE or fgt_init is None or fgt_get_sensorChannelsInfo is None:
        if FLUIGENT_SDK_IMPORT_ERROR is not None:
            print(f"[Fluigent] SDK not available: {FLUIGENT_SDK_IMPORT_ERROR}")
        return []

    if force_reinit:
        _close_fluigent_sdk()

    fgt_init()
    sensors = []

    try:
        sensorInfoArray, sensorTypeArray = fgt_get_sensorChannelsInfo()

        for i, sensorInfo in enumerate(sensorInfoArray):
            if sensorInfo.DeviceSN == 0:
                break
            idx = sensorInfo.index
            sn = str(sensorInfo.DeviceSN)
            print(f"[Fluigent] Sensor detected -> Index={idx}, SN={sn}, Type={sensorTypeArray[i]}")
            sensors.append(FluigentPressureSensor(index=idx, device_sn=sn))

    except Exception as e:
        print(f"[Fluigent] Failed to initialize Fluigent sensors: {e}")

    return sensors
