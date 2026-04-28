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

call :find_python
if errorlevel 1 (
    echo No compatible Python 3.10+ interpreter was found.
    echo Install Python 3.11, or set MF_PYTHON_EXE to an existing python.exe before starting this launcher.
    goto fail
)
echo Bootstrap Python: %MF_BASE_PYTHON%
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
    "%MF_BASE_PYTHON%" -m venv "%ENV_DIR%"
    if errorlevel 1 exit /b %errorlevel%
)

set "PYTHONNOUSERSITE=1"
"%ENV_DIR%\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip setuptools wheel
if errorlevel 1 exit /b %errorlevel%

"%ENV_DIR%\Scripts\python.exe" -m pip install --disable-pip-version-check --progress-bar off -r "%REQ_FILE%"
if errorlevel 1 exit /b %errorlevel%

echo.
exit /b 0

:find_python
set "MF_BASE_PYTHON="

if not "%MF_PYTHON_EXE%"=="" (
    set "MF_BASE_PYTHON=%MF_PYTHON_EXE%"
    call :validate_python
    if not errorlevel 1 exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%P in ('py -3 -c "import sys, venv; print(sys.executable)" 2^>nul') do set "MF_BASE_PYTHON=%%P"
    call :validate_python
    if not errorlevel 1 exit /b 0
)

for /f "delims=" %%P in ('where python 2^>nul') do (
    set "MF_BASE_PYTHON=%%P"
    call :validate_python
    if not errorlevel 1 exit /b 0
)

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\anaconda3\python.exe"
    "%USERPROFILE%\AppData\Local\anaconda3\python.exe"
    "%LOCALAPPDATA%\spyder-6\python.exe"
    "%USERPROFILE%\AppData\Local\spyder-6\python.exe"
    "C:\ProgramData\anaconda3\python.exe"
) do (
    if exist "%%~P" (
        set "MF_BASE_PYTHON=%%~P"
        call :validate_python
        if not errorlevel 1 exit /b 0
    )
)

set "MF_BASE_PYTHON="
exit /b 1

:validate_python
if "%MF_BASE_PYTHON%"=="" exit /b 1
"%MF_BASE_PYTHON%" -c "import sys, venv; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
exit /b %errorlevel%

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
echo You can override the bootstrap Python with MF_PYTHON_EXE.
popd
exit /b 1
