# Program Editor

The editor builds JSON automation programs for the main Microfluidic System Controller.

It can run in two modes:

- embedded from the main GUI through `editor_main_embedded.py`
- standalone through `editor/editor_main.py`

## Main Components

- `editor_tasklist.py`: shows available standard and special task buttons.
- `editor_joblist.py`: stores the editable step list, supports save/load, undo/redo, copy/delete, and display formatting.
- `editor_tasks.py`: standard task dialogs such as pressure, valves, waits, measurement, export, loops, dosing, zeroing, and rotary valve actions.
- `special_tasks.py`: advanced dialogs such as pressure ramps, `PolynomialPressure`, flow control, sequence loading, and Fluigent calibration.
- `editor_step.py`: small step data object.
- `task_globals.py`: shared editor device catalogs supplied by the main GUI or fallback standalone defaults.

The JSON step names and common parameter keys are defined in `modules/program_contract.py`. Keep editor serialization and `ProgramRunner` behavior aligned through that contract.