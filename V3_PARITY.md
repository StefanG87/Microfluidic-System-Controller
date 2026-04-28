# V3 Functional Parity Plan

The v3 GUI is now startable and uses a separate PySide6/Fluent runtime path.
This file tracks the remaining work needed before v3 can replace the classic
PyQt5 lab GUI.

## Already Covered In V3

- Separate `main_gui_v3.py` entry point.
- Isolated v3 package environment and startup/check scripts.
- Light Fluent-style main window with navigation, cards, status strip, and Qt6 plot panel.
- Manual Modbus connection, hardware-profile loading, device refresh, pressure commands, valve commands, sampling, CSV export, and JSON program execution through `ProgramRunner`.
- Live sensor overview for latest pressure, flow, Fluigent, and generic measurement-channel values.
- Pressure offset display, manual offset saving, and internal-pressure zeroing.

## Required Before Lab Replacement

- Port the rotary valve UI/controller integration to PySide6 and wire it into `V3RuntimeController`.
- Port the specialized program-editor dialogs instead of relying only on the generic JSON editor shell.
- Add parity for classic measurement-stop behavior, including the expected manual export workflow.
- Add full Fluigent zeroing and calibration dialogs to v3.
- Add hardware profile selection using the same saved preferences workflow as the classic GUI.
- Add GUI-level safeguards while measurement or program execution is active.
- Validate pressure, valves, Fluigent sensors, flow sensors, rotary valve, CSV export, and program abort/restart behavior on the lab setup.

## Design Direction

V3 should avoid a dark oscilloscope-only look. The target is a clean scientific
workbench: bright panels, high-contrast measurement traces, calm blue/green
status colors, and clear grouping for hardware controls.
