
import json
import os
import time

from editor.modules.editor.task_globals import get_available_valves
from modules.program_contract import (
    PARAM_ACTION,
    PARAM_CONDITION,
    PARAM_CONTINUOUS,
    PARAM_DELTA_MBAR,
    PARAM_DURATION,
    PARAM_END_PRESSURE,
    PARAM_END_STEP,
    PARAM_FILENAME,
    PARAM_FILENAME_PREFIX,
    PARAM_FLOW_SENSOR,
    PARAM_FLUIDIC_VALVE,
    PARAM_FOLDER,
    PARAM_INPUT_PRESSURE,
    PARAM_KD,
    PARAM_KI,
    PARAM_KP,
    PARAM_MAX_PRESSURE,
    PARAM_MIN_PRESSURE,
    PARAM_PATH,
    PARAM_PNEUMATIC_VALVE,
    PARAM_PORT,
    PARAM_PRESSURE,
    PARAM_REPETITIONS,
    PARAM_SENSOR,
    PARAM_STABLE_TIME,
    PARAM_START_PRESSURE,
    PARAM_START_STEP,
    PARAM_STATUS,
    PARAM_TARGET_FLOW,
    PARAM_TARGET_VALUE,
    PARAM_TARGET_VOLUME,
    PARAM_TIME_SEC,
    PARAM_TOLERANCE,
    PARAM_TOLERANCE_PERCENT,
    PARAM_VALVE_NAME,
    PARAM_WAIT,
    ROTARY_ACTION_GOTO,
    ROTARY_ACTION_HOME,
    ROTARY_ACTION_NEXT,
    ROTARY_ACTION_PREV,
    STATUS_OPEN,
    STEP_ADD_PRESSURE,
    STEP_CALIBRATE_WITH_FLUIGENT_SENSOR,
    STEP_DOSE_VOLUME,
    STEP_EXPORT_CSV,
    STEP_FLOW_CONTROLLER,
    STEP_LOAD_SEQUENCE,
    STEP_LOOP,
    STEP_PRESSURE_RAMP,
    STEP_POLYNOMIAL_PRESSURE,
    STEP_ROTARY_VALVE,
    STEP_SET_PRESSURE,
    STEP_SET_PRESSURE_ZERO,
    STEP_START_MEASUREMENT,
    STEP_STOP_MEASUREMENT,
    STEP_VALVE,
    STEP_WAIT,
    STEP_WAIT_FOR_SENSOR_EVENT,
    STEP_ZERO_FLUIGENT,
    sampling_interval_ms_from_params,
)
from modules.csv_exporter import CSVExporter
from modules.polynomial_pressure import (
    apply_slew_limit,
    clamp_pressure,
    clamp_symmetric,
    describe_pressure_function,
    evaluate_pressure_target,
    is_open_loop_sensor,
    normalize_polynomial_pressure_params,
)

class ProgramRunner:
    """
    Execute microfluidic JSON programs produced by the editor.
    """

    def __init__(self, gui):
        self.gui = gui
        self.steps = []
        self.running = False
        self._log = self.gui.append_log
    @staticmethod
    def _rv_wrap_target(current_port, num_ports, delta):
        """Wrap a relative rotary move into the valid port range 1..N."""
        if not num_ports:
            return 0
        return ((int(current_port) - 1 + int(delta)) % int(num_ports)) + 1

    def load_program(self, path):
        """Load a JSON program file into `self.steps` and validate its top-level shape."""
        self._log = self.gui.append_log
        try:
            with open(path, "r", encoding="utf-8") as f:
                steps = json.load(f)
            if not isinstance(steps, list):
                raise ValueError("Invalid program format. Expected a list of steps.")
            self.steps = steps
            self._log(f"Loaded program: {path} ({len(self.steps)} steps)")
            return True
        except Exception as e:
            self._log(f"Error loading program: {e}")
            return False

    def run_program(self, log_callback=None):
        """Execute the currently loaded program step by step."""
        if log_callback is not None:
            self._log = log_callback

        self.running = True
        try:
            for step in self.steps:
                if not self.running:
                    break
                if not step.get("active", True):
                    continue
                self._log(f"-> {step.get('type')}: {step.get('params', {})}")
                self.execute_step(step, log_callback=self._log)
        finally:
            self.running = False
            self._log = self.gui.append_log

    def execute_step(self, step, log_callback=None):
        """Execute a single program step dictionary produced by the editor."""
        if log_callback is not None:
            self._log = log_callback

        type_ = step.get("type", "")
        params = step.get("params", {}) or {}

        if type_ == STEP_SET_PRESSURE:
            value = float(params.get(PARAM_PRESSURE, 0.0))
            self.gui.set_target_pressure_mbar(value)
            self._log(f"Pressure set to {value} mbar")
            return  # End the step cleanly.

        elif type_ == STEP_ADD_PRESSURE:
            delta = params.get(PARAM_DELTA_MBAR, 0.0)
            # Use the current target setpoint, not the measured value.
            current = self.gui.get_target_pressure_mbar()
            new_value = float(current) + float(delta)
            self.gui.set_target_pressure_mbar(new_value)
            self._log(f"Pressure increased by {delta} mbar -> {new_value} mbar")
            return

        elif type_ == STEP_SET_PRESSURE_ZERO:
            self.gui.set_target_pressure_mbar(0.0)
            self._log("Set pressure to 0 mbar")
            return

        elif type_ == STEP_VALVE:
            valve_name = params.get(PARAM_VALVE_NAME, "")
            if not valve_name and params.get("valve_number") is not None:
                valve_name = self._valve_name_from_legacy_number(params.get("valve_number"))
            status = params.get(PARAM_STATUS, "Open")
            state = str(status).lower() == STATUS_OPEN.lower()
            self.control_valve(valve_name, state)
            self._log(f"Valve {valve_name} set to {status}")
            return

        elif type_ == STEP_WAIT:
            seconds = float(params.get(PARAM_TIME_SEC, 1.0))
            self._log(f"Waiting for {seconds} seconds")
            time.sleep(seconds)
            return

        elif type_ == STEP_WAIT_FOR_SENSOR_EVENT:
            sensor_name = params.get(PARAM_SENSOR)
            condition = params.get(PARAM_CONDITION)
            target_value = params.get(PARAM_TARGET_VALUE, 0.0)
            tolerance = params.get(PARAM_TOLERANCE, 0.0)
            stable_time = params.get(PARAM_STABLE_TIME, 0.0)
            self._log(f"Waiting for sensor: {sensor_name} ({condition} {target_value} +/-{tolerance} for {stable_time}s)")
            self.wait_for_stable_sensor(sensor_name, condition, target_value, tolerance, stable_time)
            return

        elif type_ == STEP_START_MEASUREMENT:
            sampling_interval_ms = sampling_interval_ms_from_params(params)
            self.gui.start_measurement_from_program(sampling_interval_ms=sampling_interval_ms)
            if sampling_interval_ms is not None:
                self._log(f"Measurement started ({sampling_interval_ms} ms interval)")
            else:
                self._log("Measurement started")
            return

        elif type_ == STEP_STOP_MEASUREMENT:
            self.gui.stop_measurement_from_program()
            self._log("Measurement stopped")
            return

        elif type_ == STEP_EXPORT_CSV:
            self.export_csv(params)
            return

        elif type_ == STEP_PRESSURE_RAMP:
            self.ramp_pressure(params)
            return

        elif type_ == STEP_POLYNOMIAL_PRESSURE:
            self.polynomial_pressure(params)
            return

        elif type_ == STEP_FLOW_CONTROLLER:
            self.flow_controller(params)
            return

        elif type_ == STEP_ZERO_FLUIGENT:
            selected_sns = params.get("sensors", [])
            self._log(f"Zeroing Fluigent sensors: {selected_sns if selected_sns else 'All'}")
            zeroed, failed = self.gui.zero_fluigent_sensors_by_name(selected_sns)
            for sensor_tag in zeroed:
                self._log(f"Sensor {sensor_tag} zeroed")
            for sensor_tag, error in failed:
                self._log(f"Failed to zero {sensor_tag}: {error}")
            return

        elif type_ == STEP_CALIBRATE_WITH_FLUIGENT_SENSOR:
            sensor_name = params.get(PARAM_SENSOR, "")
            sensor = self.gui.get_fluigent_sensor_by_name(sensor_name)
            if sensor is None:
                self._log(f"Sensor {sensor_name} not found.")
                return

            internal_pressure = self.gui.read_internal_pressure_mbar()
            if internal_pressure is None:
                self._log("Calibration failed: internal pressure readout error.")
                return

            ext_pressure = sensor.read_pressure()
            if ext_pressure is None:
                self._log("Calibration failed: sensor readout error.")
                return

            offset = self.gui.set_offset_mbar(
                internal_pressure - ext_pressure,
                persist=True,
                ignore_persist_errors=True,
            )
            self._log(f"Offset set to {offset:.2f} mbar using {sensor_name}")
            return

        elif type_ == STEP_LOOP:
            start_step = max(1, int(params.get(PARAM_START_STEP, 1)))
            end_step = max(start_step, int(params.get(PARAM_END_STEP, start_step)))
            repetitions = max(1, int(params.get(PARAM_REPETITIONS, 1)))
            start_idx = max(0, start_step - 1)
            end_idx = min(len(self.steps), end_step)
            loop_steps = self.steps[start_idx:end_idx]
            self._log(f"Loop: steps {start_step} to {end_step}, repeated {repetitions}x")
            for loop_index in range(repetitions):
                if not self.running:
                    break
                self._log(f"Loop iteration {loop_index + 1}/{repetitions}")
                for nested_step in loop_steps:
                    if not self.running:
                        break
                    if nested_step is step:
                        continue
                    if nested_step.get("active", True):
                        self.execute_step(nested_step, log_callback=self._log)
            self._log("Loop finished.")
            return

        elif type_ == STEP_DOSE_VOLUME:
            sensor_name = params.get(PARAM_FLOW_SENSOR, "")
            pneumatic_valve = params.get(PARAM_PNEUMATIC_VALVE, "")
            fluidic_valve = params.get(PARAM_FLUIDIC_VALVE, "")
            target_volume = float(params.get(PARAM_TARGET_VOLUME, 0.0))
            input_pressure = float(params.get(PARAM_INPUT_PRESSURE, 0.0))

            if pneumatic_valve:
                self.control_valve(pneumatic_valve, True)
            if fluidic_valve:
                self.control_valve(fluidic_valve, True)

            self.gui.set_target_pressure_mbar(input_pressure)
            self._log(f"Input pressure set to {input_pressure} mbar")

            volume_ul = 0.0
            last_time = time.time()
            self._log(f"Dosing target: {target_volume} uL")

            while self.running and volume_ul < target_volume:
                flow = self.get_flow_value(sensor_name)  # uL/min
                now = time.time()
                dt = now - last_time
                last_time = now

                if flow is not None:
                    volume_ul += (flow / 60.0) * dt  # uL/s * s = uL

                time.sleep(0.1)

            if fluidic_valve:
                self.control_valve(fluidic_valve, False)
            self._log(f"Dose complete: {volume_ul:.1f} uL (target: {target_volume} uL)")
            return

        elif type_ == STEP_ROTARY_VALVE:
            action = (params.get(PARAM_ACTION) or "goto").lower()

            if action == ROTARY_ACTION_HOME:
                self._log("Rotary Valve: Home")
                self.gui.home_rotary_from_program()
                return

            if action in (ROTARY_ACTION_PREV, ROTARY_ACTION_NEXT):
                delta = -1 if action == ROTARY_ACTION_PREV else +1
                num_ports, current_port = self.gui.get_rotary_state_from_program()
                if not (num_ports and current_port):
                    self._log("Rotary Valve: cannot compute relative target (not homed or unknown state).")
                    return
                target = self._rv_wrap_target(current_port, num_ports, delta)
                self._log(f"Rotary Valve: {action} -> Goto {target}")
                self.gui.goto_rotary_from_program(target, wait=True)
                return

            if action == ROTARY_ACTION_GOTO:
                port = int(params.get(PARAM_PORT, 1))
                wait = bool(params.get(PARAM_WAIT, True))
                self._log(f"Rotary Valve: Goto {port} (wait={wait})")
                self.gui.goto_rotary_from_program(port, wait=wait)
                return

            self._log(f"Unknown Rotary Valve action: {action}")
            return

        elif type_ == STEP_LOAD_SEQUENCE:
            self.load_sequence(params)
            return

        self._log(f"Unsupported step type: {type_}")

    def ramp_pressure(self, params):
        """
        Execute a pressure-ramp step.
        """
        p_start = params.get(PARAM_START_PRESSURE, 0.0)
        p_end = params.get(PARAM_END_PRESSURE, 100.0)
        duration = params.get(PARAM_DURATION, 10.0)
        steps = int(duration / 0.2)
        if steps < 1:
            steps = 1

        for i in range(steps + 1):
            if not self.running:
                break
            p = p_start + (p_end - p_start) * i / steps
            self.gui.set_target_pressure_mbar(p)
            time.sleep(0.2)

    
    def polynomial_pressure(self, params):
        """Execute a time-dependent pressure profile, optionally with sensor feedback."""
        cfg = normalize_polynomial_pressure_params(params)
        duration = cfg["duration"]
        if duration <= 0.0:
            self._log("PolynomialPressure skipped: duration must be greater than 0 s.")
            return

        sensor_name = cfg["sensor"]
        closed_loop = not is_open_loop_sensor(sensor_name)
        previous_target = clamp_pressure(
            self.gui.get_target_pressure_mbar(),
            cfg["clamp_min"],
            cfg["clamp_max"],
        )
        previous_command = previous_target

        control_text = "open-loop actuator target"
        if closed_loop:
            control_text = (
                f"closed-loop on {sensor_name}, Kp={cfg['feedback_gain']:g}, "
                f"max correction={cfg['max_correction']:g} mbar"
            )
        self._log(
            f"PolynomialPressure: {describe_pressure_function(cfg)}, duration {duration:g}s, "
            f"clamp {cfg['clamp_min']:g}..{cfg['clamp_max']:g} mbar, "
            f"slew <= {cfg['slew_limit']:g} mbar/s, {control_text}"
        )

        start = time.monotonic()
        last_update = start
        next_log = start
        sample_count = 0
        target_clamp_count = 0
        target_slew_count = 0
        command_clamp_count = 0
        command_slew_count = 0
        final_target = previous_target
        final_command = previous_command

        while self.running:
            now = time.monotonic()
            elapsed = min(now - start, duration)
            raw_target = evaluate_pressure_target(cfg, elapsed)
            clamped_target = clamp_pressure(raw_target, cfg["clamp_min"], cfg["clamp_max"])
            if abs(clamped_target - raw_target) > 1e-9:
                target_clamp_count += 1

            dt = max(0.0, now - last_update)
            if sample_count == 0 and cfg["slew_limit"] > 0.0:
                limited_target = previous_target
            else:
                limited_target = apply_slew_limit(clamped_target, previous_target, dt, cfg["slew_limit"])
            if abs(limited_target - clamped_target) > 1e-9:
                target_slew_count += 1
            limited_target = clamp_pressure(limited_target, cfg["clamp_min"], cfg["clamp_max"])

            measured = None
            correction = 0.0
            command_target = limited_target
            if closed_loop:
                measured = self.get_sensor_value(sensor_name)
                if measured is None:
                    self._log(f"PolynomialPressure aborted: pressure sensor {sensor_name} not available.")
                    return
                error = limited_target - float(measured)
                correction = clamp_symmetric(cfg["feedback_gain"] * error, cfg["max_correction"])
                command_target = limited_target + correction

            clamped_command = clamp_pressure(command_target, cfg["clamp_min"], cfg["clamp_max"])
            if abs(clamped_command - command_target) > 1e-9:
                command_clamp_count += 1

            if sample_count == 0 and cfg["slew_limit"] > 0.0:
                limited_command = previous_command
            else:
                limited_command = apply_slew_limit(clamped_command, previous_command, dt, cfg["slew_limit"])
            if abs(limited_command - clamped_command) > 1e-9:
                command_slew_count += 1
            limited_command = clamp_pressure(limited_command, cfg["clamp_min"], cfg["clamp_max"])

            # Plot/export should show the desired pressure curve. The hardware command may
            # differ in closed-loop mode because it includes the bounded feedback correction.
            self.gui.target_pressure = limited_target
            self.gui.pressure_source.setDesiredPressure(limited_command + self.gui.offset)

            previous_target = limited_target
            previous_command = limited_command
            final_target = limited_target
            final_command = limited_command
            last_update = now
            sample_count += 1

            if now >= next_log or elapsed >= duration:
                if closed_loop:
                    self._log(
                        f"PolynomialPressure t={elapsed:.2f}s raw={raw_target:.2f} mbar "
                        f"target={limited_target:.2f} mbar sensor={measured:.2f} mbar "
                        f"cmd={limited_command:.2f} mbar corr={correction:.2f} mbar"
                    )
                else:
                    self._log(
                        f"PolynomialPressure t={elapsed:.2f}s raw={raw_target:.2f} mbar "
                        f"target={limited_target:.2f} mbar"
                    )
                next_log = now + 1.0

            if elapsed >= duration:
                break

            self._sleep_abortable(min(cfg["sample_interval"], duration - elapsed))

        if not self.running:
            self._log(f"PolynomialPressure aborted at target {final_target:.2f} mbar.")
            return

        self._log(
            f"PolynomialPressure finished: {sample_count} setpoints, final target {final_target:.2f} mbar, "
            f"final command {final_command:.2f} mbar "
            f"(target clamped {target_clamp_count}x, target slew-limited {target_slew_count}x, "
            f"command clamped {command_clamp_count}x, command slew-limited {command_slew_count}x)."
        )
    def _sleep_abortable(self, seconds, quantum=0.05):
        """Sleep in short chunks so manual program stop requests are handled promptly."""
        deadline = time.monotonic() + max(0.0, float(seconds))
        while self.running:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            time.sleep(min(float(quantum), remaining))
    def flow_controller(self, params):
        """
        Run the PID-based flow-control step.
        """
        sensor_name = params.get(PARAM_SENSOR, "")
        target_flow = params.get(PARAM_TARGET_FLOW, 50.0)
        p_max = params.get(PARAM_MAX_PRESSURE, 350.0)
        p_min = params.get(PARAM_MIN_PRESSURE, 0.0)
        tolerance_percent = params.get(PARAM_TOLERANCE_PERCENT, 10.0)
        stable_time = params.get(PARAM_STABLE_TIME, 5.0)
        continuous = params.get(PARAM_CONTINUOUS, False)
        
        # PID parameters from the step or the conservative defaults.
        Kp = params.get(PARAM_KP, 0.1)
        Ki = params.get(PARAM_KI, 0.1)
        Kd = params.get(PARAM_KD, 0.05)
    
        tolerance = target_flow * (tolerance_percent / 100.0)
        current_pressure = self.gui.get_target_pressure_mbar()
        self._log(
            f"PID flow control: target {target_flow} uL/min, sensor {sensor_name}, "
            f"tolerance +/-{tolerance:.2f}, stable time {stable_time}s"
        )
        
        # PID state variables.
        integral = 0.0
        last_error = 0.0
        stable_counter = 0
        sampling_interval = 0.5  # Interval for checking the current flow.
    
        while self.running:  # Continuous Mode
            # Read the current flow from the selected flow-sensor channel.
            flow = self.get_flow_value(sensor_name)
            if flow is None:
                self._log(f"Sensor {sensor_name} not found or not responding.")
                break
    
            error = target_flow - flow
            self._log(f"Flow: {flow:.2f} uL/min, target: {target_flow:.2f} uL/min, error: {error:.2f}")
    
            # === PID control ===
            dt = sampling_interval
            integral += error * dt  # Accumulate the integral term.
            derivative = (error - last_error) / dt  # Rate of change term.
            last_error = error
    
            # Apply the PID adjustment and clamp it to the allowed pressure range.
            adjustment = (Kp * error) + (Ki * integral) + (Kd * derivative)
            current_pressure += adjustment
            current_pressure = max(p_min, min(p_max, current_pressure))
            self.gui.set_target_pressure_mbar(current_pressure)
            # Check stability only when not running in continuous mode.
            if not continuous:
                if abs(error) <= tolerance:
                    stable_counter += 1
                    if stable_counter * sampling_interval >= stable_time:
                        self._log(f"Stable flow achieved: {flow:.2f} uL/min (+/-{tolerance:.2f}) for {stable_time}s")
                        break
                else:
                    stable_counter = 0  # Reset if the flow leaves the stable range.
            # Wait before the next control iteration.
            time.sleep(sampling_interval)
            # Exit condition for the normal non-continuous mode.
            if not continuous and stable_counter * sampling_interval >= stable_time:
                break
    
        self._log(f"Flow control finished. Final pressure: {current_pressure} mbar.")
    
    def get_flow_value(self, sensor_name):
        """
        Return the current value of the selected flow sensor.
        """
        return self.gui.read_flow_sensor_value(sensor_name)
    
   
    def wait_for_stable_sensor(self, sensor_name, condition, target_value, tolerance, stable_time):
        """
        For condition == "Stable":
          - evaluate stability relative to the rolling window center (median)
            over the last `stable_time` seconds
          - use median-of-3 prefiltering plus an in-band fraction around the median
          - reject slowly drifting traces by checking the rolling-window slope
          - return immediately once the last `stable_time` seconds satisfy all criteria

        For >, <, = : preserve the classic threshold logic with a dwell time.
        """
        import statistics
        from collections import deque
    
        # --- Polling interval for this wait loop (adjust to your sensor update rate) ---
        sample_interval = 0.2  # seconds
    
        # --- Short window (for short-term noise sanity) & long window (the target stable_time span) ---
        # Median-of-3 prefilter suppresses single-sample spikes before any windowing.
        use_median3  = True
        raw3         = deque(maxlen=3)
    
        # Short window (2..10 s) for short-term noise check to avoid "jittery stability".
        short_sec    = 5.0
        short_sec    = max(2.0, min(short_sec, 10.0))
        short_len    = max(10, int(short_sec / sample_interval))
        short_buf    = deque(maxlen=short_len)
    
        # Long window equals the requested stability time (e.g., 60 s).
        long_sec     = max(stable_time, short_sec)
        long_len     = max(int(long_sec / sample_interval), short_len)
        long_buf     = deque(maxlen=long_len)
        long_tstamps = deque(maxlen=long_len)  # times (sec) relative to loop start, for slope
    
        # --- Robustness parameters ---
        # Allow up to 5% of points outside the +/-tolerance band around the window median.
        allowed_outlier_frac = 0.05
    
        # Slope tolerance (units per second): how much drift across stable_time is acceptable.
        # Heuristic: allow ~0.5 * tolerance total change over the full stable_time.
        slope_tol_per_s = (0.5 * tolerance) / max(stable_time, 1.0)
    
        # --- Helpers ---
        def median_of_3(x):
            """Median-of-3 prefilter to attenuate single-sample spikes."""
            if not use_median3:
                return x
            raw3.append(x)
            if len(raw3) < 3:
                return x
            s = sorted(raw3)
            return s[1]
    
        def robust_center_and_inband_fraction(values, tol):
            """
            Return (median, fraction_in_band), where fraction_in_band counts points
            within +/-tol of the median. Median gives a robust center.
            """
            if not values:
                return None, 0.0
            med = statistics.median(values)
            in_band = sum(1 for v in values if abs(v - med) <= tol)
            return med, in_band / len(values)
    
        def ols_slope(xs, ys):
            """Ordinary least squares slope of y vs. x (x in seconds)."""
            n = len(xs)
            if n < 3:
                return 0.0
            mean_x = sum(xs) / n
            mean_y = sum(ys) / n
            num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
            den = sum((x - mean_x) ** 2 for x in xs)
            if den == 0:
                return 0.0
            return num / den  # units per second
    
        # --- Logging throttle to avoid spamming the console ---
        last_log_epoch = 0
    
        # --- Classic dwell deadline for >, <, = conditions ---
        deadline = None
        t0 = time.time()
    
        while self.running:
            v_raw = self.get_sensor_value(sensor_name)
            if v_raw is None:
                self._log(f"Sensor {sensor_name} not found or not responding.")
                break
    
            if condition == "Stable":
                # 1) Prefilter + window updates
                v = median_of_3(v_raw)
                short_buf.append(v)
                now = time.time()
                long_buf.append(v)
                long_tstamps.append(now - t0)
    
                # 2) Only evaluate once the long window is filled (i.e., we have stable_time worth of data)
                if len(long_buf) == long_buf.maxlen:
                    # Robust band check around the median over the rolling long window
                    center, frac_in = robust_center_and_inband_fraction(list(long_buf), tolerance)
                    band_ok = (frac_in >= (1.0 - allowed_outlier_frac))
    
                    # Drift check (near-zero slope across the rolling long window)
                    slope = ols_slope(list(long_tstamps), list(long_buf))
                    drift_ok = (abs(slope) <= slope_tol_per_s)
    
                    # Short-term noise sanity (avoid declaring "stable" while visibly jittering)
                    if short_buf:
                        mean_short = sum(short_buf) / len(short_buf)
                        std_short  = statistics.pstdev(short_buf) if len(short_buf) > 1 else 0.0
                        max_dev    = max(abs(x - mean_short) for x in short_buf)
                    else:
                        std_short = 0.0
                        max_dev   = 0.0
                    noise_ok = (std_short <= (tolerance / 2.0)) and (max_dev <= tolerance)
    
                    all_ok = band_ok and drift_ok and noise_ok
    
                    # 3) Decision: IMMEDIATE success as soon as the rolling long window satisfies all criteria
                    if all_ok:
                        self._log(
                            f"Stable sensor window for {sensor_name} ({stable_time:.0f}s): "
                            f"center~{center:.2f}, in-band={frac_in*100:.1f}%, "
                            f"slope={slope:.4f}/s (tol={slope_tol_per_s:.4f}/s), "
                            f"std_s={std_short:.2f}, max_dev_s={max_dev:.2f}"
                        )
                        return
                    else:
                        # Throttled diagnostic logging (~1 line/sec)
                        if int(now) != int(last_log_epoch):
                            reasons = []
                            if not band_ok:
                                reasons.append(f"in-band={frac_in*100:.1f}%< {(1.0 - allowed_outlier_frac)*100:.1f}%")
                            if not drift_ok:
                                reasons.append(f"|slope|={abs(slope):.4f}/s>{slope_tol_per_s:.4f}/s")
                            if not noise_ok:
                                reasons.append(f"noise std={std_short:.2f}, max_dev={max_dev:.2f}>tol={tolerance:.2f}")
                            self._log("Not stable yet: " + ", ".join(reasons))
                            last_log_epoch = now
    
            else:
                # --- Classic threshold conditions with dwell time ---
                ok = self.is_condition_met(v_raw, condition, target_value, tolerance)
                if ok:
                    if deadline is None:
                        deadline = time.time() + stable_time
                    if time.time() >= deadline:
                        self._log(
                            f"{sensor_name} met condition '{condition} {target_value}+/-{tolerance}' "
                            f"for {stable_time:.1f}s"
                        )
                        return
                else:
                    deadline = None
    
            time.sleep(sample_interval)


     
    def is_condition_met(self, value, condition, target, tolerance):
        """Check whether a threshold-style sensor condition is satisfied."""
        if condition == ">":
            return value > (target + tolerance)
        elif condition == "<":
            return value < (target - tolerance)
        elif condition == "=":
            return abs(value - target) <= tolerance
        return False

    def get_sensor_value(self, sensor_name):
        return self.gui.read_program_sensor_value(sensor_name)
     
    def load_sequence(self, params):
        """Load a JSON sequence and inject its steps directly into the running program."""
        filename = params.get(PARAM_FILENAME)
        filepath = params.get(PARAM_PATH, filename)  # Use the explicit path when the editor provided one.

        if not filepath:
            self._log("No sequence file specified.")
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                loaded_steps = json.load(f)

            if not isinstance(loaded_steps, list):
                self._log("Invalid sequence format. Expected a list of steps.")
                return

            self._log(f"Loading sequence: {filepath} ({len(loaded_steps)} steps)")
            # Inject the loaded steps directly into the current program list.
            for loaded_step in loaded_steps:
                if not self.running:
                    break
                if loaded_step.get("active", True):  # Execute only active steps from the loaded sequence.
                    self.execute_step(loaded_step, log_callback=self._log)

        except Exception as e:
            self._log(f"Error loading sequence: {str(e)}")

    def _valve_name_from_legacy_number(self, valve_number):
        """Map old `valve_number` program parameters to the current valve name list."""
        try:
            index = int(valve_number) - 1
        except (TypeError, ValueError):
            return ""

        available_valves = get_available_valves()
        if 0 <= index < len(available_valves):
            return available_valves[index]
        return ""

    def control_valve(self, valve_name, state):
        """
        Control a valve by its editor-visible name.
        :param valve_name: Display name such as "Pneumatic 1" or "Fluidic 6"
        :param state: True to open the valve, False to close it
        """
        available_valves = get_available_valves()
        if self.gui.set_valve_state_by_name(valve_name, state, available_valves):
            self._log(f"Valve {valve_name} set to {'Open' if state else 'Closed'}")
        else:
            self._log(f"Valve {valve_name} not found in available valves: {available_valves}")

    def stop(self):
        """Stop the running program without resetting hardware state."""
        self.running = False
        self._log("Program execution manually stopped.")

    def stop_all(self):
        """Stop the program and reset valves and pressure to their default state."""
        self.running = False
        self._log("Program execution manually stopped.")

        # Keep the existing stop-all semantics: close valves and send a raw 0 mbar setpoint.
        self.gui.close_all_valves()
        self.gui.reset_pressure_hardware_zero_mbar()
        self._log("All valves closed, pressure set to 0 mbar.")

    def export_csv(self, params):
        folder = params.get(PARAM_FOLDER) or CSVExporter.ensure_measurements_folder()
        prefix = params.get(PARAM_FILENAME_PREFIX, "measurement")

        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as exc:
            self._log(f"CSV export failed: could not create folder {folder}: {exc}")
            return

        path = CSVExporter.generate_filename(prefix=prefix, folder=folder)
        self.gui.export_csv_from_program(path)
        self._log(f"CSV export saved to:\n{path}")


