@echo off
setlocal EnableExtensions

title Microfluidic System Controller v3
color 0F

echo ============================================================
echo Microfluidic System Controller v3
echo ============================================================
echo.
echo This launcher uses an isolated local Python environment.
echo It does not use Spyder or the currently active shell environment.
echo.

call "%~dp0start_v3.bat"
set "EXIT_CODE=%errorlevel%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Launcher finished normally.
) else (
    echo Launcher finished with error code %EXIT_CODE%.
    echo.
    echo Please check:
    echo %LOCALAPPDATA%\MicrofluidicSystemController\logs\start_v3_last.log
    echo %LOCALAPPDATA%\MicrofluidicSystemController\logs\check_v3_last.log
)

echo.
echo Press any key to close this window.
pause >nul
exit /b %EXIT_CODE%
