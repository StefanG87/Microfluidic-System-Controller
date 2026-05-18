# Manual Testing Checklist

This project controls real laboratory hardware. These checks are intended as a lightweight validation routine before using a changed software version for measurements.

## Before Starting

- Confirm the active Git commit or tag.
- Confirm the correct hardware profile is selected.
- Confirm pressure tubing and reservoirs are safe for the planned pressure range.
- Start with pressure at 0 mbar and all valves closed.
- Keep an emergency stop / power-off option reachable.

## Hardware-Free Regression Checks

Run these before lab testing after changes to the v3 program runner, preferences, or UI wiring:

```powershell
.\.venv-v3\Scripts\python.exe -B -m unittest tests.test_program_runner_stop tests.test_program_runner_rotary tests.test_rotary_controller tests.test_preferences tests.test_hardware_profiles tests.test_v3_plot_panel tests.test_v3_program_editor tests.test_v3_sensor_card
```

The stop tests cover abortable `Wait`, `Pressure Ramp`, `PolynomialPressure`, `Wait for Sensor Event`, `Dose Volume`, `Load Sequence`, and continuous `Flow Controller` steps without touching hardware. The rotary tests verify JSON dispatch for `home`, `goto`, `next`, `prev`, and the `wait` flag, plus controller-level wait/timeout behavior using a fake serial device. The hardware-profile tests verify that lookup profiles remain usable by the GUI, editor, plot, and CSV layer.

After changes to calibration, balance, or v3 optional measurement channels, also run:

```powershell
.\.venv-v3\Scripts\python.exe -B -m unittest tests.test_balance tests.test_medium_calibration_core tests.test_v3_calibration_tab
```

## Classic Startup Checks

1. Start `main_gui.py`.
2. Confirm the GUI opens without import errors.
3. Confirm the Modbus connection is established or shows a clear connection error.
4. Confirm the selected hardware profile is correct.
5. Confirm detected sensors are plausible for the current setup.
6. Confirm the plot updates while the GUI remains responsive.

## V3 Cockpit Checks

1. Start `Launch_MF_Controller_v3.bat` or `start_v3.bat`.
2. Confirm v3 opens in the saved hardware profile and attempts the saved hardware connection.
3. Confirm the Dashboard shows pressure control, recording/export, three program favorites, live sensors, routine valves, and rotary controls without needing horizontal scrolling.
4. Confirm the `Valves` page shows the full active profile. For `stand1`, this means 12 pneumatic valves and 4 fluidic valves.
5. Confirm the Dashboard valve subset stays compact: the first four pneumatic valves plus all fluidic valves.
6. Open `Plot Settings` and verify plot channels are grouped by pressure, flow, Fluigent/pressure sensors, and valves/rotary.
7. Use the `Pressure`, `Pressure + Sensors`, `All`, and `Clear` plot presets and confirm the live plot updates immediately.
8. Switch time, pressure, and flow/sensor axes between `Linear` and `Log`; confirm log axes handle zero or negative values gracefully by showing only positive data on that axis.
9. Confirm the live plot legend appears above the plot whenever at least one channel is visible.
10. Confirm pan/zoom, `Autoscale`, `Lock View`, and `Refresh Plot` behave predictably during live sampling.
11. Open `Calibration` and confirm the page lists the connected pressure source, flow sensors, pressure sensors, pneumatic valves, and fluidic valves.
12. Open `Settings`, refresh serial ports, and confirm the optional balance COM port can be selected without affecting Modbus or rotary hardware.

## Basic Hardware Checks

1. Set pressure to 0 mbar.
2. Set a low pressure setpoint, for example 20 mbar, and confirm the internal readout reacts plausibly.
3. Set pressure back to 0 mbar.
4. Toggle each configured valve open and closed once.
5. If the rotary valve is connected, connect, home, and move to one known safe port.
6. If Fluigent sensors are connected, read values and optionally perform software zeroing.
7. If the Ohaus balance is connected, configure it according to the SOP: 9600 baud, 8N1, no flow control, unit g, and auto-print interval around 1 s. Connect it from v3 Settings and confirm `Read Once` returns plausible mass in g.

For the `stand1` profile, confirm all 12 pneumatic valves explicitly. The measured mapping is Valve 1-4 on coils 0-3, Valve 5-8 on coils 12-15, and Valve 9-12 on coils 8-11. `extended_pneumatic_setup` is retained only as a hidden compatibility profile.

## Program Runner Checks

1. Load a small program that only uses pressure steps up to a safe limit.
2. Run the program and confirm the stop button remains responsive.
3. Load another program after the first one finishes to confirm thread cleanup.
4. Abort one running program and confirm buttons are re-enabled.
5. Confirm the log reports errors clearly instead of freezing the GUI.

If a program appears not to stop during a rotary-valve action, note whether the step used `wait=true`. That path intentionally waits for the device to report `Done`; hardware-level timeout/abort behavior should be changed only after a controlled rotary-valve lab test.

## PolynomialPressure Checks

1. Start with open-loop mode and a small range, for example 0 to 50 mbar.
2. Confirm clamp and slew limits shown in the editor match the intended safety limits.
3. Run the profile while watching the target and measured pressure plot.
4. Test sine or higher-order profiles only with conservative clamp limits.
5. Use closed-loop feedback only after the selected pressure sensor has been verified.

## Export Checks

1. Start a measurement.
2. Stop the measurement.
3. Export CSV manually and confirm the file contains time, pressure, valve, flow, Fluigent, and rotary columns where applicable.
4. Run a programmatic export step and confirm it writes to the expected folder without opening a manual dialog.
5. If the balance is connected, confirm the CSV includes a stable `Balance [g]` column and that read-timing metadata, when enabled, records the balance read timing separately from pressure, valve, flow, and Fluigent reads.

## Calibration Checks

1. Confirm pressure is 0 mbar and all valves are closed.
2. Configure EtOH percentage, pressure stages, flow sensor, pressure sensor, pneumatic valve, fluidic valve, and optional balance COM port.
3. Start with a low-pressure dry/safe run before using real collection tubes.
4. Confirm the calibration worker closes the fluidic and pneumatic valves and sends 0 mbar after finish, stop, or failure.
5. Save the calibration JSON and confirm it is written to `calibration_EtOH/` with the expected EtOH percentage in the filename.

## After Testing

- Set pressure to 0 mbar.
- Close all valves.
- Stop measurement if it is still running.
- Note the tested commit and any observed hardware-specific behavior.
