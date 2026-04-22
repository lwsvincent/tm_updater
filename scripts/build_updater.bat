@echo off
setlocal

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe
set SOURCE_FILE=%ROOT_DIR%\src\updater\main.py
set OUTPUT_DIR=%ROOT_DIR%\dist

if not exist "%VENV_PYTHON%" (
    echo [ERROR] venv not found at %VENV_PYTHON%
    echo Please create the venv first: python -m venv .venv
    pause
    exit /b 1
)

echo Checking Nuitka installation...
"%VENV_PYTHON%" -m nuitka --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Nuitka not installed. Run: pip install nuitka
    pause
    exit /b 1
)

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo.
echo Building updater.exe with Nuitka...
echo Source : %SOURCE_FILE%
echo Output : %OUTPUT_DIR%\updater.exe
echo.

"%VENV_PYTHON%" -m nuitka ^
    --onefile ^
    --mingw64 ^
    --disable-ccache ^
    --show-scons ^
    --jobs=1 ^
    --output-filename=updater.exe ^
    --output-dir="%OUTPUT_DIR%" ^
    --include-package=packaging ^
    --windows-console-mode=force ^
    --assume-yes-for-downloads ^
    "%SOURCE_FILE%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo Build successful: %OUTPUT_DIR%\updater.exe
pause
