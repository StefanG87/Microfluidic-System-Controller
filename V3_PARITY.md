# V3 Functional Parity Plan

The v3 GUI is now startable and uses a separate PySide6/Fluent runtime path.
This file tracks the remaining work needed before v3 can replace the classic
PyQt5 lab GUI.

## Already Covered In V3

- Separate `main_gui_v3.py` entry point.
- Isolated v3 package environment and startup/check scripts.
- Light Fluent-style main window with navigation, cards, status strip, and Qt6 plot panel.
- Manual Modbus connection, hardware-profile loading, device refresh, pressure commands, valve commands, sampling, CSV export, and JSON program execution through `ProgramRunner`.
- Hardware connection is visible on the Dashboard and Pressure Control pages, and unsafe pressure/sampling/valve actions are disabled until connected.
- The v3 GUI attempts to connect hardware automatically on startup using the saved Modbus/profile settings; manual connect/disconnect remains available.
- Live sensor rows are rebuilt from the runtime device catalog after hardware discovery, before the first sample arrives.
- Live sensor overview for latest pressure, flow, Fluigent, and generic measurement-channel values.
- Live plot sampling now follows the classic GUI model: data updates continuously after hardware connection, `Refresh Plot` starts a clean plot buffer/timebase, pressure/flow/Fluigent/valve channels are selectable and persisted, rotary active-port bands can be shown, the legend sits outside the plot, and Matplotlib zoom/pan can be used during live updates.
- The Dashboard is again focused on the lab cockpit workflow: pressure control, recording/export, live sensor values, valve switching, and rotary control in one view; sampling interval/export/hardware/offset settings live in Settings.
- Rotary valve control is visible again in the main cockpit and uses the same controller layer as the classic PyQt5 widget, without importing PyQt5 into v3.
- Settings contains a v2-style pressure-offset calibration dialog for internal pressure or Fluigent reference sensors.
- The v3 editor window now follows the old editor workflow more closely: task palette on the left, program step list and duplicate/update/remove controls on the right.
- The v3 editor has native PySide6 parameter dialogs for standard tasks, special tasks, valve/sensor selection, rotary actions, CSV export, loops, dose volume, flow control, and PolynomialPressure parameters with live preview.
- Settings can select hardware profiles from `lookup/*.json` or load an explicit profile JSON file while idle.
- The v3 window performs a safe hardware shutdown on close: stop program/measurement, close valves, send raw pressure 0, and close Modbus.
- Pressure offset display, manual offset saving, and internal-pressure zeroing.
- Program runner favorite slots, program-state button locking, and a manual stop-to-CSV export workflow.

## Required Before Lab Replacement

- Lab-test rotary valve reconnect/control and active-port plotting on the real setup.
- Lab-test Fluigent zeroing and calibration program steps from v3-generated programs.
- Add GUI-level safeguards while measurement or program execution is active.
- Validate pressure, valves, Fluigent sensors, flow sensors, rotary valve, CSV export, and program abort/restart behavior on the lab setup.

## Design Direction

V3 should avoid a dark oscilloscope-only look. The target is a clean scientific
workbench: bright panels, high-contrast measurement traces, one restrained
accent color, and clear grouping for hardware controls.
