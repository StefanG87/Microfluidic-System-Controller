@echo off
setlocal

call "%~dp0install_all_packages.bat" --v3-only %*
exit /b %errorlevel%
