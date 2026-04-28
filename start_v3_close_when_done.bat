@echo off
setlocal

call "%~dp0start_v3.bat" --close-when-done
exit /b %errorlevel%
