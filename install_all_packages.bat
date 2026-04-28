@echo off
setlocal EnableExtensions

pushd "%~dp0" || exit /b 1

set "MODE=all"
set "RESET=0"
if "%MF_CONTROLLER_ENV_ROOT%"=="" set "MF_CONTROLLER_ENV_ROOT=%LOCALAPPDATA%\MicrofluidicSystemController"
set "MF_CLASSIC_ENV=%MF_CONTROLLER_ENV_ROOT%\classic-pyqt5"
set "MF_V3_ENV=%MF_CONTROLLER_ENV_ROOT%\v3-pyside6"

:parse_args
if "%~1"=="" goto run_install
if /I "%~1"=="--reset" (
    set "RESET=1"
    shift
    goto parse_args
)
if /I "%~1"=="--classic-only" (
    set "MODE=classic"
    shift
    goto parse_args
)
if /I "%~1"=="--v3-only" (
    set "MODE=v3"
    shift
    goto parse_args
)
echo Unknown option: %~1
goto fail

:run_install
echo Repository: %CD%
echo Environment root: %MF_CONTROLLER_ENV_ROOT%
echo.

if /I not "%MODE%"=="v3" (
    call :install_env "%MF_CLASSIC_ENV%" "requirements.txt" "classic PyQt5 runtime"
    if errorlevel 1 goto fail
)

if /I not "%MODE%"=="classic" (
    call :install_env "%MF_V3_ENV%" "requirements-v3.txt" "v3 PySide6 runtime"
    if errorlevel 1 goto fail

    call :check_v3_imports
    if errorlevel 1 goto fail
)

echo.
echo Package installation completed successfully.
popd
exit /b 0

:install_env
set "ENV_DIR=%~1"
set "REQ_FILE=%~2"
set "LABEL=%~3"

echo === Installing %LABEL% ===
if "%RESET%"=="1" if exist "%ENV_DIR%" (
    echo Removing existing %ENV_DIR%
    rmdir /s /q "%ENV_DIR%"
    if errorlevel 1 exit /b %errorlevel%
)

if not exist "%ENV_DIR%\Scripts\python.exe" (
    py -3 -m venv "%ENV_DIR%"
    if errorlevel 1 exit /b %errorlevel%
)

set "PYTHONNOUSERSITE=1"
"%ENV_DIR%\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip setuptools wheel
if errorlevel 1 exit /b %errorlevel%

"%ENV_DIR%\Scripts\python.exe" -m pip install --disable-pip-version-check --progress-bar off -r "%REQ_FILE%"
if errorlevel 1 exit /b %errorlevel%

echo.
exit /b 0

:check_v3_imports
echo === Checking v3 Qt imports ===
set "V3_ENV=%MF_V3_ENV%"
set "PYTHONNOUSERSITE=1"
set "QT_API=pyside6"
set "QT_PLUGIN_PATH="
set "QML2_IMPORT_PATH="
set "PATH=%V3_ENV%\Scripts;%V3_ENV%\Lib\site-packages\PySide6;%PATH%"

"%V3_ENV%\Scripts\python.exe" -c "from PySide6 import QtCore; import qfluentwidgets; import ui_v3.main_window; print('v3 import check ok:', QtCore.qVersion())"
exit /b %errorlevel%

:fail
echo.
echo Package installation failed.
echo If v3 Qt DLL imports fail after a partial install, rerun:
echo install_all_packages.bat --v3-only --reset
echo.
echo You can override the local environment folder with MF_CONTROLLER_ENV_ROOT.
popd
exit /b 1
