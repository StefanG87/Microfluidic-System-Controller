@echo off
setlocal

call conda activate mf_controller_build
if errorlevel 1 (
    echo [ERROR] Could not activate conda environment mf_controller_build
    pause
    exit /b 1
)

cd /d "%~dp0"

echo ==========================================
echo   Build uF Controller 2.2 + uF Editor 2.2
echo ==========================================
echo.

if not exist "main_gui.py" (
    echo [ERROR] main_gui.py not found
    pause
    exit /b 1
)

if not exist "editor\editor_main.py" (
    echo [ERROR] editor\editor_main.py not found
    pause
    exit /b 1
)

if not exist "icons\MFController.ico" (
    echo [ERROR] icons\MFController.ico not found
    pause
    exit /b 1
)

if not exist "editor\icons\MFEditor.ico" (
    echo [ERROR] editor\icons\MFEditor.ico not found
    pause
    exit /b 1
)

if not exist "uF_Controller_2_2.spec" (
    echo [ERROR] uF_Controller_2_2.spec not found
    pause
    exit /b 1
)

if not exist "uF_Editor_2_2.spec" (
    echo [ERROR] uF_Editor_2_2.spec not found
    pause
    exit /b 1
)

echo [INFO] Cleaning old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%LOCALAPPDATA%\pyinstaller" rmdir /s /q "%LOCALAPPDATA%\pyinstaller"

echo.
echo [INFO] Building controller...
pyinstaller ^
  --noconfirm ^
  --clean ^
  uF_Controller_2_2.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Controller build failed.
    pause
    exit /b 1
)

echo.
echo [INFO] Building editor...
pyinstaller ^
  --noconfirm ^
  --clean ^
  uF_Editor_2_2.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Editor build failed.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Build finished successfully
echo ==========================================
echo.
echo Controller:
echo   dist\uF_Controller_2_2\uF_Controller_2_2.exe
echo.
echo Editor:
echo   dist\uF_Editor_2_2\uF_Editor_2_2.exe
echo.
pause
