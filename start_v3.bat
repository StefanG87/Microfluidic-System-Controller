@echo off
setlocal EnableExtensions

pushd "%~dp0" || (
    echo Could not open the repository folder.
    pause
    exit /b 1
)

if "%MF_CONTROLLER_ENV_ROOT%"=="" set "MF_CONTROLLER_ENV_ROOT=%LOCALAPPDATA%\MicrofluidicSystemController"
set "V3_ENV=%MF_CONTROLLER_ENV_ROOT%\v3-pyside6"
set "LOG_DIR=%MF_CONTROLLER_ENV_ROOT%\logs"
set "START_LOG=%LOG_DIR%\start_v3_last.log"
set "CHECK_LOG=%LOG_DIR%\check_v3_last.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ============================================== > "%START_LOG%"
echo Microfluidic System Controller v3 start log >> "%START_LOG%"
echo Repo: %CD% >> "%START_LOG%"
echo Env root: %MF_CONTROLLER_ENV_ROOT% >> "%START_LOG%"
echo Date: %DATE% %TIME% >> "%START_LOG%"
echo ============================================== >> "%START_LOG%"

if not exist "%V3_ENV%\Scripts\python.exe" (
    echo Local v3 environment not found. Creating it now...
    call "%~dp0install_all_packages.bat" --v3-only >> "%START_LOG%" 2>&1
    if errorlevel 1 goto fail
)

call "%~dp0check_v3.bat" > "%CHECK_LOG%" 2>&1
if errorlevel 1 (
    echo v3 environment check failed. See:
    echo   %CHECK_LOG%
    goto fail
)

set "PYTHONNOUSERSITE=1"
set "QT_API=pyside6"
set "QT_PLUGIN_PATH="
set "QML2_IMPORT_PATH="
set "PATH=%V3_ENV%\Scripts;%V3_ENV%\Lib\site-packages\PySide6;%PATH%"

echo Launching v3 GUI...
"%V3_ENV%\Scripts\python.exe" main_gui_v3.py >> "%START_LOG%" 2>&1
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" goto fail

popd
exit /b 0

:fail
echo.
echo v3 did not start correctly.
echo Start log:
echo   %START_LOG%
if exist "%CHECK_LOG%" (
    echo Check log:
    echo   %CHECK_LOG%
)
echo.
echo The window stays open so the error can be read.
pause
popd
exit /b 1
