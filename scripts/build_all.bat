@echo off
setlocal

set SCRIPT_DIR=%~dp0

echo Starting parallel build processes...

echo [1/2] Launching GUI build...
start "Build GUI" /D "%SCRIPT_DIR%" cmd /c build_gui.bat

echo [2/2] Launching Updater build...
start "Build Updater" /D "%SCRIPT_DIR%" cmd /c build_updater.bat

echo.
echo Both build processes have been started in separate windows.
echo Please check the individual windows for build status.
