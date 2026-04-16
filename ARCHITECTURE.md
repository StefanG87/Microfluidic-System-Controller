# Architecture Overview

## Program summary

The application is a laboratory control and monitoring GUI for a microfluidic measurement setup. It combines live hardware control, sensor acquisition, plotting, CSV export, and program execution inside one PyQt5 desktop application.

## Runtime flow

1. `main_gui.py` starts `PressureFlowGUI`.
2. `PressureFlowGUI` connects to Modbus hardware, builds valve objects from the selected hardware profile, detects sensors, and starts a periodic Qt timer.
3. The timer calls `update_data()`, which samples hardware values, updates internal buffers, refreshes labels, and triggers plot updates.
4. Measurement buffers are exported through `ExportDialog` and `CSVExporter`.
5. Automation programs are loaded from JSON, executed by `ProgramRunner`, and hosted in a worker thread through `ProgramWorker`.

## Main modules

### GUI and orchestration

- `modules/gui_window.py`: main controller window and runtime coordinator
- `modules/plot_area.py`: live Matplotlib plot widget
- `modules/measurement_session.py`: measurement-buffer owner and `ExportSnapshot` provider for plotting/CSV data
- `modules/sampling_manager.py`: shared time base and sampling dialog
- `modules/export_dialog.py`: CSV export UI
- `modules/csv_exporter.py`: filename and export folder helpers

### Hardware interfaces

- `modules/pressure_controller.py`: pressure controller abstraction
- `modules/valve.py`: coil-based valve abstraction
- `modules/flow_sensor.py`: analog flow sensor conversion and readout
- `modules/fluigent_wrapper.py`: Fluigent sensor discovery and access
- `modules/rotary_valve_controller.py`: rotary valve communication wrapper
- `modules/rotary_valve_widget.py`: rotary valve GUI and polling
- `modules/rvm_dt.py`: low-level rotary valve protocol helpers
- `modules/mf_common.py`: shared persistence, small UI helpers, and hardware profile loading

### Automation and editor

- `modules/program_runner.py`: executes JSON program steps against the active GUI/hardware state
- `modules/program_worker.py`: worker-thread wrapper for program execution
- `editor/modules/editor/editor_tasklist.py`: task palette
- `editor/modules/editor/editor_joblist.py`: step list, editing, save/load
- `editor/modules/editor/editor_tasks.py`: standard task parameter dialogs
- `editor/modules/editor/special_tasks.py`: advanced task parameter dialogs
- `editor/modules/editor/editor_step.py`: step data model
- `editor/modules/editor/task_globals.py`: shared editor device catalogs
- `editor_main_embedded.py`: integrated editor host
- `editor/editor_main.py`: standalone editor host

## Editor and runner contract

The editor serializes step dictionaries into JSON, and `ProgramRunner` consumes those dictionaries directly. The current parameter contract is:

- `Set Pressure`: `pressure` in mbar
- `Add Pressure`: `delta_mbar` in mbar
- `Set Pressure to 0`: no parameters
- `Valve`: `valve_name`, `status` (`Open` or `Close`)
- `Wait`: `time_sec`
- `Wait for Sensor Event`: `sensor`, `condition`, `target_value`, `tolerance`, `stable_time`
- `Start Measurement`: `sampling_interval_ms` in milliseconds inside the step JSON; legacy `sampling_rate` values are still read as Hz and converted for old programs
- `Stop Measurement`: no parameters
- `Export CSV`: `filename_prefix`, `folder`
- `Pressure Ramp`: `start_pressure`, `end_pressure`, `duration`
- `PolynomialPressure`: `mode`, `order`, `coefficients`, `duration`, `clamp_min`, `clamp_max`, `slew_limit`, `sample_interval`
- `Flow Controller`: `sensor`, `target_flow`, `max_pressure`, `min_pressure`, `tolerance_percent`, `stable_time`, `continuous`, optional PID gains
- `ZeroFluigent`: `sensors`, where an empty list means all detected Fluigent sensors
- `Calibrate With Fluigent Sensor`: `sensor`
- `Loop`: `start_step`, `end_step`, `repetitions`
- `Load Sequence`: `filename`, `path`
- `Dose Volume`: `flow_sensor`, `pneumatic_valve`, `fluidic_valve`, `target_volume`, `input_pressure`
- `Rotary Valve`: `action`, optional `port`, optional `wait`

This contract is centralized in `modules/program_contract.py`. The module defines the persisted step names, parameter keys, and the legacy sampling-rate conversion used by both editor and runner code.

## Current boundaries and coupling

### Strong couplings that exist today

- `PressureFlowGUI` owns UI state, device state, plotting coordination, export orchestration, and program bootstrapping; measurement buffers and export snapshots are now grouped in `MeasurementSession`.
- `PressureFlowGUI` exposes narrow runtime methods for automation pressure control, sensor reads, valve writes, measurement start/stop, CSV export, and rotary-valve program actions.
- `ProgramRunner` uses those runtime methods for hardware-facing actions and now only keeps step dispatch, flow-control loops, and program-specific control flow.
- Editor availability data is published globally through `task_globals.py`.
- Resource and import resolution still depend partly on startup-time path bootstrapping.

### Why that matters

These couplings are workable for the current application but make behavior harder to reason about, especially around hidden failures, path handling, and task/runtime parameter consistency.

## Confirmed cleanup already worth preserving

- Sampling dialog imports were repaired.
- Plot reset now has an explicit interface instead of relying on a swallowed missing-method error.
- Editor sensor-event display now uses `target_value` consistently.
- Embedded editor device publication now goes through one central task-global update path.
- Runner CSV export uses one central filename helper.
- Program-runner smoke test programs are available in `test_programs/`.

## Recommended next refactor direction

1. Keep `PressureFlowGUI` as the main window, but move narrow responsibilities into helpers rather than rewriting the app.
2. Align editor task parameters with runtime execution semantics.
3. Centralize project-root/resource helpers and reduce `sys.path` manipulation.
4. Fix the programmatic `Stop Measurement` path so it does not open the manual export dialog.
5. Replace broad exception swallowing in the highest-value paths first.
6. Add a few hardware-free smoke tests for editor serialization and runner step dispatch.
