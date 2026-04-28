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

A parallel v3 GUI track is available through `main_gui_v3.py`. It uses PySide6
and Fluent Widgets in a separate Qt6 path so the stable PyQt5 lab GUI remains
available while the modern interface reaches functional parity.

## Main Entry Points

- `main_gui.py`: starts the main controller GUI.
- `main_gui_v3.py`: starts the parallel PySide6/Fluent v3 GUI shell.
- `editor_main_embedded.py`: integrated editor window launched from the controller.
- `editor/editor_main.py`: standalone program editor.

## Project Structure

- `modules/`: runtime package for GUI, hardware interfaces, plotting, export, pressure profiles, and program execution.
- `ui_v3/`: parallel PySide6/Fluent interface with navigation, control cards, Qt6 plot panel, controller facades, and a JSON-compatible editor shell.
- `editor/`: standalone and embedded program editor package.
- `lookup/`: hardware profiles and local preference data.
- `icons/` and `editor/icons/`: GUI icon assets.
- `Measurements/`: runtime CSV output folder, ignored by Git.
- `ARCHITECTURE.md`: current module and program-contract documentation.
- `TESTING.md`: manual validation checklist for the lab setup.

## Important Architectural Notes

- `modules/gui_window.py` is still the main orchestration point for UI, hardware lifecycle, buffering, export, and automation startup.
- `modules/measurement_session.py` owns live measurement buffers, generic extra measurement series, and CSV export snapshots.
- `modules/device_catalog.py` is the preferred place to publish editor-visible runtime devices, display names, units, and profile-derived valve metadata when new hardware modules are added; existing pressure, flow, Fluigent, valve, and rotary devices use the same descriptor pattern.
- The main GUI `Update Config` button refreshes detected sensors and editor device lists when no measurement or program is active.
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

Install the experimental v3 dependencies from `requirements-v3.txt`, then start
the parallel Qt6 GUI:

```bash
py -3 main_gui_v3.py
```

For a clean local v3 environment that does not modify the classic PyQt5 setup,
use:

```bash
setup_v3_env.bat
check_v3.bat
start_v3.bat
```

The installer creates local environments under
`%LOCALAPPDATA%\MicrofluidicSystemController` by default. This keeps large Qt
packages and DLLs off the network repository path. Set `MF_CONTROLLER_ENV_ROOT`
before running the installer if another local location is preferred.

On a lab computer, the repository can stay on the network drive. Only the
Python environments are created locally per Windows user in `%LOCALAPPDATA%`.
`start_v3.bat` now creates the local v3 environment automatically if it is
missing, runs a quick import check, and keeps the console open if startup fails.

To install both the classic PyQt5 environment and the v3 PySide6 environment,
use:

```bash
install_all_packages.bat
```

If a previous v3 install produced Qt DLL import errors, rebuild only the v3
environment:

```bash
install_all_packages.bat --v3-only --reset
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
- Register new sensors and actuators through `DeviceCatalog` descriptor helpers before wiring them into editor tasks, plotting, or CSV export.
- Keep device display names and measurement units in `DeviceCatalog` constants/helpers instead of duplicating strings across GUI and editor modules.
- For future time-series devices such as a balance, register a named extra series in `MeasurementSession` so the CSV exporter can add one stable column per device signal.
- Keep advanced pressure-profile behavior documented when `PolynomialPressure` changes.
- Reduce broad `try/except` blocks where clearer logging can preserve stability without hiding root causes.
- Further separate GUI orchestration from hardware and automation helpers only in small, low-risk steps.
- Revisit package/resource bootstrapping if PyInstaller packaging becomes part of the regular workflow again.
