@echo off
setlocal EnableExtensions

title Microfluidic System Controller v3
color 0F

call :enter_repo "%~dp0" || (
    echo Could not open the repository folder.
    echo.
    echo Script folder:
    echo   %~dp0
    echo.
    echo If this was started from a UNC path, map the share to a drive letter
    echo or start the launcher from the mapped drive, for example Z:.
    echo.
    pause
    exit /b 1
)

echo ============================================================
echo Microfluidic System Controller v3
echo ============================================================
echo.
echo This launcher uses an isolated local Python environment.
echo It does not use Spyder or the currently active shell environment.
echo.

call "start_v3.bat"
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
popd
exit /b %EXIT_CODE%

:enter_repo
set "SCRIPT_DIR=%~1"
pushd "%SCRIPT_DIR%" >nul 2>nul
if not errorlevel 1 exit /b 0

set "MAPPED_SCRIPT_DIR="
set "MF_SCRIPT_DIR=%SCRIPT_DIR%"
for /f "usebackq delims=" %%D in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$scriptDir = [IO.Path]::GetFullPath($env:MF_SCRIPT_DIR); $drives = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.DisplayRoot }; foreach ($drive in $drives) { $root = [string]$drive.DisplayRoot; if ($scriptDir.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { $tail = $scriptDir.Substring($root.Length).TrimStart('\'); $candidate = Join-Path ($drive.Name + ':\') $tail; if (Test-Path -LiteralPath $candidate) { $candidate; break } } }"`) do set "MAPPED_SCRIPT_DIR=%%D"
if not "%MAPPED_SCRIPT_DIR%"=="" (
    pushd "%MAPPED_SCRIPT_DIR%" >nul 2>nul
    if not errorlevel 1 exit /b 0
)

exit /b 1
