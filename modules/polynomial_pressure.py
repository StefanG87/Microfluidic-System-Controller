"""Shared helpers for time-dependent pressure profiles."""

import math

DEFAULT_CLAMP_MIN_MBAR = 0.0
DEFAULT_CLAMP_MAX_MBAR = 300.0
DEFAULT_SLEW_LIMIT_MBAR_PER_S = 50.0
DEFAULT_SAMPLE_INTERVAL_S = 0.1
DEFAULT_FEEDBACK_GAIN = 0.5
DEFAULT_MAX_CORRECTION_MBAR = 50.0
CONTROL_SENSOR_OPEN_LOOP = "Open loop"
MAX_POLYNOMIAL_ORDER = 6

POLYNOMIAL_MODES = {"linear", "quadratic", "cubic", "polynomial"}
SINE_MODES = {"sine", "sin", "sinus"}


def clamp_pressure(value, minimum=DEFAULT_CLAMP_MIN_MBAR, maximum=DEFAULT_CLAMP_MAX_MBAR):
    """Clamp a pressure setpoint to the configured physical pressure range."""
    lo = float(minimum)
    hi = float(maximum)
    if hi < lo:
        lo, hi = hi, lo
    return max(lo, min(hi, float(value)))


def clamp_symmetric(value, maximum_abs):
    """Clamp a signed correction symmetrically around zero."""
    maximum_abs = max(0.0, float(maximum_abs))
    return max(-maximum_abs, min(maximum_abs, float(value)))


def evaluate_polynomial(coefficients, x):
    """Evaluate a polynomial with coefficients in ascending powers of x."""
    result = 0.0
    power = 1.0
    x = float(x)
    for coefficient in coefficients:
        result += float(coefficient) * power
        power *= x
    return result


def _float_param(params, *names, default=0.0):
    for name in names:
        if name in params and params.get(name) is not None:
            try:
                return float(params.get(name))
            except (TypeError, ValueError):
                break
    return float(default)


def _normalize_mode(mode, order):
    mode = str(mode or "").strip().lower()
    if mode in SINE_MODES:
        return "sine"
    if mode in POLYNOMIAL_MODES:
        return mode
    if int(order) == 1:
        return "linear"
    if int(order) == 2:
        return "quadratic"
    if int(order) == 3:
        return "cubic"
    return "polynomial"


def _coefficients_from_params(params, order):
    coefficients = params.get("coefficients")
    if not coefficients:
        found_indexed = any(f"c{i}" in params for i in range(MAX_POLYNOMIAL_ORDER + 1))
        if found_indexed:
            coefficients = [params.get(f"c{i}", 0.0) for i in range(order + 1)]
        elif "m" in params or "n" in params:
            coefficients = [params.get("n", 0.0), params.get("m", 0.0)]
        elif "m_mbar_per_s" in params or "n_mbar" in params:
            coefficients = [params.get("n_mbar", 0.0), params.get("m_mbar_per_s", 0.0)]
            if "a_mbar_per_s2" in params:
                coefficients.append(params.get("a_mbar_per_s2", 0.0))
            if "b_mbar_per_s3" in params:
                coefficients.append(params.get("b_mbar_per_s3", 0.0))
        else:
            coefficients = [0.0] * (order + 1)
            if order >= 1:
                coefficients[1] = 10.0

    coefficients = [float(value) for value in coefficients]
    if len(coefficients) < order + 1:
        coefficients.extend([0.0] * (order + 1 - len(coefficients)))
    elif len(coefficients) > order + 1:
        coefficients = coefficients[: order + 1]
    return coefficients


def normalize_polynomial_pressure_params(params):
    """Return normalized parameters for a PolynomialPressure step."""
    params = params or {}

    raw_order = int(params.get("order", 1))
    mode = _normalize_mode(params.get("mode"), raw_order)
    if mode == "linear":
        order = 1
    elif mode == "quadratic":
        order = 2
    elif mode == "cubic":
        order = 3
    else:
        order = max(0, min(MAX_POLYNOMIAL_ORDER, raw_order))

    duration = max(0.0, _float_param(params, "duration", default=10.0))
    clamp_min = _float_param(params, "clamp_min", default=DEFAULT_CLAMP_MIN_MBAR)
    clamp_max = _float_param(params, "clamp_max", default=DEFAULT_CLAMP_MAX_MBAR)
    slew_limit = max(0.0, _float_param(params, "slew_limit", default=DEFAULT_SLEW_LIMIT_MBAR_PER_S))
    sample_interval = max(0.01, _float_param(params, "sample_interval", default=DEFAULT_SAMPLE_INTERVAL_S))

    sensor = str(params.get("sensor") or params.get("control_sensor") or CONTROL_SENSOR_OPEN_LOOP)
    feedback_gain = _float_param(params, "feedback_gain", default=DEFAULT_FEEDBACK_GAIN)
    max_correction = max(0.0, _float_param(params, "max_correction", default=DEFAULT_MAX_CORRECTION_MBAR))

    cfg = {
        "mode": mode,
        "order": order,
        "coefficients": _coefficients_from_params(params, order),
        "duration": duration,
        "clamp_min": clamp_min,
        "clamp_max": clamp_max,
        "slew_limit": slew_limit,
        "sample_interval": sample_interval,
        "sensor": sensor,
        "feedback_gain": feedback_gain,
        "max_correction": max_correction,
        "offset_mbar": _float_param(params, "offset_mbar", "sine_offset_mbar", default=150.0),
        "amplitude_mbar": _float_param(params, "amplitude_mbar", "sine_amplitude_mbar", default=50.0),
        "period_s": max(0.001, _float_param(params, "period_s", "sine_period_s", default=max(duration, 1.0))),
        "phase_deg": _float_param(params, "phase_deg", "sine_phase_deg", default=0.0),
    }
    return cfg


def is_open_loop_sensor(sensor_name):
    """Return True when the profile should be sent directly as actuator setpoint."""
    return not sensor_name or str(sensor_name).strip().lower() in {
        "open loop",
        "open-loop",
        "none",
        "",
    }


def evaluate_pressure_target(config_or_params, x):
    """Evaluate the configured pressure target at time x in seconds."""
    cfg = config_or_params
    if "clamp_min" not in cfg or "sample_interval" not in cfg:
        cfg = normalize_polynomial_pressure_params(config_or_params)

    mode = cfg["mode"]
    if mode == "sine":
        phase = math.radians(cfg["phase_deg"])
        return cfg["offset_mbar"] + cfg["amplitude_mbar"] * math.sin(
            (2.0 * math.pi * float(x) / cfg["period_s"]) + phase
        )
    return evaluate_polynomial(cfg["coefficients"], x)


def describe_pressure_function(config_or_params):
    """Return a compact human-readable description of the configured function."""
    cfg = config_or_params
    if "clamp_min" not in cfg or "sample_interval" not in cfg:
        cfg = normalize_polynomial_pressure_params(config_or_params)

    if cfg["mode"] == "sine":
        return (
            f"P(t) = {cfg['offset_mbar']:g} + {cfg['amplitude_mbar']:g}*sin("
            f"2*pi*t/{cfg['period_s']:g} + {cfg['phase_deg']:g} deg)"
        )

    names = ["n", "m", "a", "b", "c4", "c5", "c6"]
    terms = []
    for power, coefficient in enumerate(cfg["coefficients"]):
        label = names[power] if power < len(names) else f"c{power}"
        if power == 0:
            terms.append(f"{label}={coefficient:g}")
        else:
            terms.append(f"{label}={coefficient:g}/s^{power}")
    return f"Polynomial order {cfg['order']} ({', '.join(terms)})"


def apply_slew_limit(target, previous, dt, max_rate):
    """Limit the pressure step from previous to target by max_rate * dt."""
    target = float(target)
    previous = float(previous)
    dt = max(0.0, float(dt))
    max_rate = max(0.0, float(max_rate))
    if max_rate == 0.0 or dt == 0.0:
        return target

    max_delta = max_rate * dt
    delta = target - previous
    if delta > max_delta:
        return previous + max_delta
    if delta < -max_delta:
        return previous - max_delta
    return target


def build_pressure_profile(params, initial_pressure=None, sample_interval=None):
    """Build raw, clamped, and slew-limited preview points for a pressure step."""
    cfg = normalize_polynomial_pressure_params(params)
    dt = float(sample_interval or cfg["sample_interval"])
    if dt <= 0.0:
        dt = DEFAULT_SAMPLE_INTERVAL_S

    duration = cfg["duration"]
    count = max(1, int(round(duration / dt)))
    previous = initial_pressure
    if previous is None:
        previous = clamp_pressure(
            evaluate_pressure_target(cfg, 0.0),
            cfg["clamp_min"],
            cfg["clamp_max"],
        )
    else:
        previous = clamp_pressure(previous, cfg["clamp_min"], cfg["clamp_max"])

    points = []
    for idx in range(count + 1):
        t = min(duration, idx * dt)
        raw = evaluate_pressure_target(cfg, t)
        clamped = clamp_pressure(raw, cfg["clamp_min"], cfg["clamp_max"])
        if idx == 0:
            limited = previous
        else:
            actual_dt = t - points[-1]["time"]
            limited = apply_slew_limit(clamped, previous, actual_dt, cfg["slew_limit"])
        limited = clamp_pressure(limited, cfg["clamp_min"], cfg["clamp_max"])
        points.append(
            {
                "time": t,
                "raw": raw,
                "clamped": clamped,
                "limited": limited,
            }
        )
        previous = limited

    return points
