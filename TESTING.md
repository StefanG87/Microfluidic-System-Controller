# Manual Testing Checklist

This project controls real laboratory hardware. These checks are intended as a lightweight validation routine before using a changed software version for measurements.

## Before Starting

- Confirm the active Git commit or tag.
- Confirm the correct hardware profile is selected.
- Confirm pressure tubing and reservoirs are safe for the planned pressure range.
- Start with pressure at 0 mbar and all valves closed.
- Keep an emergency stop / power-off option reachable.

## Startup Checks

1. Start `main_gui.py`.
2. Confirm the GUI opens without import errors.
3. Confirm the Modbus connection is established or shows a clear connection error.
4. Confirm the selected hardware profile is correct.
5. Confirm detected sensors are plausible for the current setup.
6. Confirm the plot updates while the GUI remains responsive.

## Basic Hardware Checks

1. Set pressure to 0 mbar.
2. Set a low pressure setpoint, for example 20 mbar, and confirm the internal readout reacts plausibly.
3. Set pressure back to 0 mbar.
4. Toggle each configured valve open and closed once.
5. If the rotary valve is connected, connect, home, and move to one known safe port.
6. If Fluigent sensors are connected, read values and optionally perform software zeroing.

## Program Runner Checks

1. Load a small program that only uses pressure steps up to a safe limit.
2. Run the program and confirm the stop button remains responsive.
3. Load another program after the first one finishes to confirm thread cleanup.
4. Abort one running program and confirm buttons are re-enabled.
5. Confirm the log reports errors clearly instead of freezing the GUI.

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

## After Testing

- Set pressure to 0 mbar.
- Close all valves.
- Stop measurement if it is still running.
- Note the tested commit and any observed hardware-specific behavior.