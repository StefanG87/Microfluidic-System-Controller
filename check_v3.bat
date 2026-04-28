@echo off
setlocal

pushd "%~dp0" || exit /b 1

if "%MF_CONTROLLER_ENV_ROOT%"=="" set "MF_CONTROLLER_ENV_ROOT=%LOCALAPPDATA%\MicrofluidicSystemController"
set "V3_ENV=%MF_CONTROLLER_ENV_ROOT%\v3-pyside6"

if not exist "%V3_ENV%\Scripts\python.exe" (
    echo v3 environment not found. Run setup_v3_env.bat first.
    popd
    exit /b 1
)

set "PYTHONNOUSERSITE=1"
set "QT_API=pyside6"
set "QT_PLUGIN_PATH="
set "QML2_IMPORT_PATH="
set "PATH=%V3_ENV%\Scripts;%V3_ENV%\Lib\site-packages\PySide6;%PATH%"

"%V3_ENV%\Scripts\python.exe" -m compileall -q main_gui_v3.py ui_v3
if errorlevel 1 goto fail

"%V3_ENV%\Scripts\python.exe" -c "from PySide6 import QtCore; import qfluentwidgets; import ui_v3.main_window; print('v3 import check ok:', QtCore.qVersion())"
if errorlevel 1 goto fail

popd
exit /b 0

:fail
popd
exit /b 1
