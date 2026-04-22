# Architecture Overview

## Program Summary

The Microfluidic System Controller is a PyQt5 desktop application for controlling and monitoring a laboratory microfluidic measurement setup. It combines pressure control, valve switching, flow and pressure sensor readout, live plotting, CSV export, and JSON-defined automation programs.

The main runtime window is `PressureFlowGUI` in `modules/gui_window.py`. The program editor can run embedded from the main GUI or standalone through `editor/editor_main.py`.

## Runtime Flow

1. `main_gui.py` bootstraps import paths for the project and bundled Fluigent SDK, creates the Qt application, and opens `PressureFlowGUI`.
2. `PressureFlowGUI` connects to the Modbus pressure/valve hardware, loads the selected hardware profile, builds valve objects, detects configured sensors, and creates the plot/export/program-runner components.
3. A Qt timer calls `update_data()`, which reads the current pressure, valves, flow sensors, Fluigent pressure sensors, and rotary-valve state into the shared measurement session.
4. `PlotArea` renders live pressure, flow, valve, Fluigent, and rotary activity data from the buffers.
5. `ExportDialog` and `CSVExporter` write snapshots of the current measurement session to CSV files.
6. Automation programs are loaded from JSON by `ProgramRunner` and executed in a worker thread through `ProgramWorker`.

## Main Modules

### GUI And Orchestration

- `modules/gui_window.py`: main controller window, hardware lifecycle, runtime state, GUI callbacks, and automation bridge methods.
- `modules/measurement_session.py`: owner for live measurement buffers and export snapshots.
- `modules/device_catalog.py`: lightweight runtime catalog for editor-visible sensors and actuators.
- `modules/plot_area.py`: Matplotlib-based live plot widget.
- `modules/sampling_manager.py`: shared time base and sampling interval dialog.
- `modules/export_dialog.py`: manual and programmatic CSV writer UI.
- `modules/csv_exporter.py`: default export folder and timestamped filename helpers.

### Hardware Interfaces

- `modules/pressure_controller.py`: pressure-controller abstraction on top of Modbus registers.
- `modules/valve.py`: coil-driven valve abstraction.
- `modules/flow_sensor.py`: analog flow sensor conversion and readout.
- `modules/fluigent_wrapper.py`: Fluigent SDK loading, sensor detection, readout, and software zeroing.
- `modules/rotary_valve_controller.py`: high-level rotary valve controller.
- `modules/rotary_valve_widget.py`: rotary valve GUI, polling, and program-runner helper methods.
- `modules/rvm_dt.py`: low-level AMF RVM DT serial protocol helper.
- `modules/mf_common.py`: shared preferences, resource/output paths, hardware profile loading, small UI helpers, and persistence helpers.

### Automation And Editor

- `modules/program_contract.py`: shared JSON step names and parameter keys used by both editor and runner.
- `modules/program_runner.py`: executes editor-generated JSON steps against the active GUI/hardware runtime.
- `modules/program_worker.py`: Qt worker wrapper around `ProgramRunner`.
- `modules/polynomial_pressure.py`: shared pressure-profile helpers for advanced pressure steps and editor previews.
- `editor/modules/editor/editor_tasklist.py`: task palette.
- `editor/modules/editor/editor_joblist.py`: editable program step list, save/load, undo/redo, and display formatting.
- `editor/modules/editor/editor_tasks.py`: standard task parameter dialogs.
- `editor/modules/editor/special_tasks.py`: advanced task dialogs, including pressure ramps, PolynomialPressure, flow control, sequence loading, and Fluigent calibration.
- `editor/modules/editor/editor_step.py`: editor step model.
- `editor/modules/editor/task_globals.py`: shared device catalog for editor dialogs.

## Editor And Runner Contract

The editor serializes program steps as JSON dictionaries. `ProgramRunner` consumes the same dictionaries directly. Persisted step names and common parameter keys live in `modules/program_contract.py`.

Current step contract:

- `Set Pressure`: `pressure` in mbar.
- `Set Pressure to 0`: no parameters.
- `Add Pressure`: `delta_mbar` in mbar.
- `Valve`: `valve_name`, `status` (`Open` or `Close`). Legacy `valve_number` is still mapped for old programs.
- `Wait`: `time_sec`.
- `Wait for Sensor Event`: `sensor`, `condition`, `target_value`, `tolerance`, `stable_time`.
- `Start Measurement`: `sampling_interval_ms`; legacy `sampling_rate` is still read as Hz and converted for old programs.
- `Stop Measurement`: no parameters.
- `Export CSV`: `filename_prefix`, optional `folder`.
- `Pressure Ramp`: `start_pressure`, `end_pressure`, `duration`.
- `PolynomialPressure`: `mode`, `order`, `coefficients`, `duration`, `clamp_min`, `clamp_max`, `slew_limit`, `sample_interval`, optional `sensor`, `feedback_gain`, `max_correction`, and sine parameters `offset_mbar`, `amplitude_mbar`, `period_s`, `phase_deg`.
- `Flow Controller`: `sensor`, `target_flow`, `max_pressure`, `min_pressure`, `tolerance_percent`, `stable_time`, `continuous`, optional PID gains `Kp`, `Ki`, `Kd`.
- `ZeroFluigent`: `sensors`; an empty list means all detected Fluigent sensors.
- `Calibrate With Fluigent Sensor`: `sensor`.
- `Loop`: `start_step`, `end_step`, `repetitions`.
- `Load Sequence`: `filename`, `path`.
- `Dose Volume`: `flow_sensor`, `pneumatic_valve`, `fluidic_valve`, `target_volume`, `input_pressure`.
- `Rotary Valve`: `action`, optional `port`, optional `wait`.

## Current Boundaries

The application is intentionally still a pragmatic lab GUI, not a fully layered service architecture. The current design keeps hardware-facing behavior conservative while moving high-value responsibilities into smaller helper modules.

Important boundaries now in place:

- Measurement buffers are grouped in `MeasurementSession` instead of being owned only as loose GUI lists.
- Runtime device names are grouped in `DeviceCatalog` before being published to editor dialogs.
- Program step names and parameter keys are centralized in `program_contract.py`.
- Pressure-profile math and preview data are centralized in `polynomial_pressure.py`.
- Program execution is hosted by `ProgramWorker`, with stale worker-thread references cleaned up after execution.
- Rotary-valve program actions go through narrow GUI helper methods so `ProgramRunner` does not manipulate the widget thread internals directly.
- CSV export path generation is centralized in `CSVExporter`.
- Icon and bundled-resource lookup is centralized through `mf_common.resource_path()`.
- Runtime output root selection for source runs and EXE builds is centralized through `mf_common.writable_app_root()`.

Strong couplings that still exist:

- `PressureFlowGUI` still owns UI widgets, hardware objects, runtime state, plotting coordination, export orchestration, and program bootstrapping.
- Editor device availability is still published through mutable module-level state in `task_globals.py`.
- Import/resource setup still partly depends on startup-time path bootstrapping for local execution and bundled SDK compatibility.
- Some hardware error paths are intentionally broad to keep the lab GUI alive, but they can hide root causes if logs are not inspected.

## Extension Pattern For New Modules

New hardware modules should be added as narrow runtime adapters first, then exposed through the shared catalog only where needed.

Recommended sequence:

1. Implement the hardware adapter in its own module, for example `syringe_pump.py` or `balance.py`.
2. Register editor-visible device names in `DeviceCatalog` using a stable role such as `syringe_pump` or `weight`.
3. Add measurement buffers only if the device produces time-series data that must be plotted or exported.
4. Add editor/program-contract constants only when the device needs automation steps.
5. Keep GUI widgets as thin controls around the adapter; avoid embedding protocol logic in `gui_window.py`.

For example, a balance should become a sensor adapter plus a `weight` catalog entry before it becomes a plot or CSV column. A syringe pump should become an actuator adapter plus a `syringe_pump` catalog entry before it gets editor tasks.

## Hardware Safety Notes

- Hardware-facing behavior should be changed conservatively and verified on the real setup.
- Pressure-setting helpers should preserve the distinction between user-facing target pressure and hardware command including offset compensation.
- Programmatic stop must not silently reset hardware unless the explicit stop-all path is used.
- Closed-loop pressure profiles should remain bounded by clamp, slew-rate, and correction limits.
- Thread cleanup is important: Qt object attributes should not shadow Qt methods such as `thread()`.

## Documentation Sources

The authoritative documentation is:

- `README.md` for project overview, setup, and workflow.
- `ARCHITECTURE.md` for module boundaries and program-contract details.
- `TESTING.md` for manual validation on the lab setup.

Historical notes are kept for context only and should not be treated as current architecture.

## Recommended Next Refactor Direction

1. Keep `PressureFlowGUI` as the main window, but move narrow responsibilities into helpers only when that reduces risk.
2. Keep `program_contract.py` and `polynomial_pressure.py` as the source of truth when new automation parameters are added.
3. Reduce broad exception swallowing in high-value paths where clearer logging can preserve stability without hiding root causes.
4. Keep project-root and resource bootstrapping minimal now that PyInstaller resource lookup has a shared helper.
5. Consider a small hardware-free runner check only if automation features continue to grow beyond manual validation.
