# Microfluidic System Controller

PyQt5 desktop application for controlling and monitoring a microfluidic laboratory setup.

## What The Application Does

The controller GUI connects to laboratory hardware over Modbus TCP and serial interfaces. It can:

- set and monitor pressure
- switch pneumatic and fluidic valves
- read analog flow sensors and Fluigent pressure sensors
- control an AMF rotary valve
- display live plots for pressure, flow, valves, Fluigent sensors, and rotary valve activity
- export measurements to CSV
- execute JSON-defined automation programs from the integrated program editor

The main runtime window is `PressureFlowGUI` in `modules/gui_window.py`.

## Main Entry Points

- `main_gui.py`: starts the main controller GUI.
- `editor_main_embedded.py`: integrated editor window launched from the controller.
- `editor/editor_main.py`: standalone program editor.

## Project Structure

- `modules/`: runtime package for GUI, hardware interfaces, plotting, export, pressure profiles, and program execution.
- `editor/`: standalone and embedded program editor package.
- `lookup/`: hardware profiles and local preference data.
- `icons/` and `editor/icons/`: GUI icon assets.
- `Measurements/`: runtime CSV output folder, ignored by Git.
- `ARCHITECTURE.md`: current module and program-contract documentation.
- `TESTING.md`: manual validation checklist for the lab setup.

## Important Architectural Notes

- `modules/gui_window.py` is still the main orchestration point for UI, hardware lifecycle, buffering, export, and automation startup.
- `modules/measurement_session.py` owns live measurement buffers and builds CSV export snapshots.
- `modules/program_contract.py` defines the shared editor/runner step names and parameter keys.
- `modules/program_runner.py` executes editor-generated JSON steps through narrow runtime methods exposed by the GUI.
- `modules/polynomial_pressure.py` contains shared helpers for polynomial and sine pressure profiles, including clamp, slew limiting, and optional feedback correction.
- Editor task metadata is currently shared through `editor/modules/editor/task_globals.py`.
- Hardware-facing behavior should be changed conservatively and verified on real equipment.

## Running Locally

Typical dependencies are listed in `requirements.txt`.

Start the main GUI:

```bash
py -3 main_gui.py
```

Start the standalone editor:

```bash
py -3 editor/editor_main.py
```

## Building Windows EXEs

The repository includes PyInstaller specs for the controller and standalone editor:

```bash
build_all_exe.bat
```

The build script expects the `mf_controller_build` conda environment and uses:

- `uF_Controller_2_2.spec`
- `uF_Editor_2_2.spec`

Generated `build/` and `dist/` folders are ignored by Git.

Before using a changed version on the lab setup, run through the manual checks in `TESTING.md`.

## Repository Workflow

This project is maintained in a private GitHub repository:

`https://github.com/StefanG87/Microfluidic-System-Controller`

Recommended workflow:

1. Commit source, profiles, icons, and documentation.
2. Keep build outputs, runtime measurements, caches, and local preference files out of Git.
3. Use small commits for hardware-related changes.
4. Tag software versions used for important experiments or publications.
5. Document any behavior-changing hardware update in `ARCHITECTURE.md` or `TESTING.md`.

## Current Follow-Up Priorities

- Keep editor parameters and runtime behavior aligned through `program_contract.py`.
- Keep advanced pressure-profile behavior documented when `PolynomialPressure` changes.
- Reduce broad `try/except` blocks where clearer logging can preserve stability without hiding root causes.
- Further separate GUI orchestration from hardware and automation helpers only in small, low-risk steps.
- Revisit package/resource bootstrapping if PyInstaller packaging becomes part of the regular workflow again.
