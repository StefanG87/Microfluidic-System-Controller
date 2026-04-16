"""Shared contract for editor-generated automation program steps.

The editor serializes these exact string values into JSON and ProgramRunner
consumes them at runtime. Keep this module free of Qt and hardware imports so
it can be reused from both editor and runtime code.
"""

# Step type names persisted in program JSON files.
STEP_SET_PRESSURE = "Set Pressure"
STEP_SET_PRESSURE_ZERO = "Set Pressure to 0"
STEP_ADD_PRESSURE = "Add Pressure"
STEP_VALVE = "Valve"
STEP_WAIT = "Wait"
STEP_WAIT_FOR_SENSOR_EVENT = "Wait for Sensor Event"
STEP_START_MEASUREMENT = "Start Measurement"
STEP_STOP_MEASUREMENT = "Stop Measurement"
STEP_EXPORT_CSV = "Export CSV"
STEP_PRESSURE_RAMP = "Pressure Ramp"
STEP_FLOW_CONTROLLER = "Flow Controller"
STEP_ZERO_FLUIGENT = "ZeroFluigent"
STEP_CALIBRATE_WITH_FLUIGENT_SENSOR = "Calibrate With Fluigent Sensor"
STEP_LOOP = "Loop"
STEP_LOAD_SEQUENCE = "Load Sequence"
STEP_DOSE_VOLUME = "Dose Volume"
STEP_ROTARY_VALVE = "Rotary Valve"

STANDARD_STEP_NAMES = [
    STEP_SET_PRESSURE,
    STEP_SET_PRESSURE_ZERO,
    STEP_ADD_PRESSURE,
    STEP_VALVE,
    STEP_WAIT,
    STEP_WAIT_FOR_SENSOR_EVENT,
    STEP_START_MEASUREMENT,
    STEP_EXPORT_CSV,
    STEP_ZERO_FLUIGENT,
    STEP_LOOP,
    STEP_DOSE_VOLUME,
    STEP_ROTARY_VALVE,
]

SPECIAL_STEP_NAMES = [
    STEP_PRESSURE_RAMP,
    STEP_FLOW_CONTROLLER,
    STEP_LOAD_SEQUENCE,
    STEP_CALIBRATE_WITH_FLUIGENT_SENSOR,
]

# Common parameter keys persisted in program JSON files.
PARAM_PRESSURE = "pressure"
PARAM_DELTA_MBAR = "delta_mbar"
PARAM_VALVE_NAME = "valve_name"
PARAM_STATUS = "status"
PARAM_TIME_SEC = "time_sec"
PARAM_SENSOR = "sensor"
PARAM_CONDITION = "condition"
PARAM_TARGET_VALUE = "target_value"
PARAM_TOLERANCE = "tolerance"
PARAM_STABLE_TIME = "stable_time"
PARAM_SAMPLING_INTERVAL_MS = "sampling_interval_ms"
PARAM_LEGACY_SAMPLING_RATE = "sampling_rate"
PARAM_FILENAME_PREFIX = "filename_prefix"
PARAM_FOLDER = "folder"
PARAM_START_STEP = "start_step"
PARAM_END_STEP = "end_step"
PARAM_REPETITIONS = "repetitions"
PARAM_FLOW_SENSOR = "flow_sensor"
PARAM_PNEUMATIC_VALVE = "pneumatic_valve"
PARAM_FLUIDIC_VALVE = "fluidic_valve"
PARAM_TARGET_VOLUME = "target_volume"
PARAM_INPUT_PRESSURE = "input_pressure"
PARAM_SENSORS = "sensors"
PARAM_ACTION = "action"
PARAM_PORT = "port"
PARAM_WAIT = "wait"
PARAM_START_PRESSURE = "start_pressure"
PARAM_END_PRESSURE = "end_pressure"
PARAM_DURATION = "duration"
PARAM_TARGET_FLOW = "target_flow"
PARAM_MAX_PRESSURE = "max_pressure"
PARAM_MIN_PRESSURE = "min_pressure"
PARAM_TOLERANCE_PERCENT = "tolerance_percent"
PARAM_CONTINUOUS = "continuous"
PARAM_FILENAME = "filename"
PARAM_PATH = "path"
PARAM_KP = "Kp"
PARAM_KI = "Ki"
PARAM_KD = "Kd"

STATUS_OPEN = "Open"
STATUS_CLOSE = "Close"
CONDITION_STABLE = "Stable"

ROTARY_ACTION_GOTO = "goto"
ROTARY_ACTION_HOME = "home"
ROTARY_ACTION_PREV = "prev"
ROTARY_ACTION_NEXT = "next"


def sampling_interval_ms_from_params(params, default=None):
    """Return the step sampling interval in ms, converting legacy Hz values when needed."""
    interval_ms = params.get(PARAM_SAMPLING_INTERVAL_MS)
    if interval_ms is None and params.get(PARAM_LEGACY_SAMPLING_RATE) is not None:
        try:
            interval_ms = max(1, int(round(1000.0 / float(params.get(PARAM_LEGACY_SAMPLING_RATE)))))
        except (TypeError, ValueError, ZeroDivisionError):
            interval_ms = default
    if interval_ms is None:
        return default
    return max(1, int(interval_ms))
