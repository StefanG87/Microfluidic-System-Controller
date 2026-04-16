# Microfluidic System Controller

PyQt5 desktop application for controlling and monitoring a microfluidic laboratory setup.

## What the application does

The controller GUI connects to laboratory hardware over Modbus TCP and serial interfaces. It can:

- set and monitor pressure
- switch pneumatic and fluidic valves
- read analog flow sensors and Fluigent pressure sensors
- display live plots for pressure, flow, valves, and rotary valve activity
- export measurements to CSV
- execute JSON-defined automation programs from the integrated program editor

The main runtime window is `PressureFlowGUI` in `modules/gui_window.py`.

## Main entry points

- `main_gui.py`: starts the main controller GUI
- `editor_main_embedded.py`: integrated editor window launched from the controller
- `editor/editor_main.py`: standalone program editor

## Project structure

- `modules/`: explicit runtime package for GUI, hardware interfaces, plotting, export, and runner logic
- `editor/` and `editor/modules/editor/`: explicit editor packages for the standalone and embedded program editor
- `lookup/`: hardware profiles and local preferences
- `icons/`: GUI icons
- `Measurements/`: exported measurement files at runtime
- `build/`, `dist/`, `editor/dist/`: generated build artifacts

## Important architectural notes

- `modules/gui_window.py` is currently the main orchestration point for UI, hardware lifecycle, buffering, export, and automation startup.
- `modules/program_runner.py` executes editor-generated JSON steps and calls back into the GUI and hardware abstractions.
- Editor task metadata is currently shared through `editor/modules/editor/task_globals.py`.
- Hardware-facing behavior should be changed conservatively and verified on real equipment.

## Running locally

Typical dependencies are listed in `requirements.txt`.

Start the main GUI:

```bash
py -3 main_gui.py
```

Start the standalone editor:

```bash
py -3 editor/editor_main.py
```

## Git and GitHub recommendation

A private GitHub repository is strongly recommended for this project.

Benefits:

- traceable changes for hardware-sensitive code
- safer incremental refactoring via branches and pull requests
- reproducible software versions for measurement campaigns
- issue tracking for architecture and bug follow-up

Suggested first repository workflow:

1. Keep the repository private.
2. Commit only source, profiles, icons, and documentation.
3. Ignore build outputs, runtime measurements, caches, and local preference files.
4. Use small branches for hardware-related changes.
5. Tag versions used for experiments or publications.

## Current follow-up priorities

- align editor parameters with runtime behavior for `Start Measurement` and `Pressure Ramp`
- reduce broad `try/except` blocks that currently hide failures
- replace remaining `sys.path` bootstrapping with a more explicit package layout
- further separate GUI orchestration from hardware and automation services
