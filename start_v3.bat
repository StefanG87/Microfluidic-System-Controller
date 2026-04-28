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

"%V3_ENV%\Scripts\python.exe" main_gui_v3.py
set EXIT_CODE=%errorlevel%
popd
exit /b %EXIT_CODE%
