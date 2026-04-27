@echo off
setlocal

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe
set SOURCE_FILE=%ROOT_DIR%\src\updater\gui\app.py
set FRONTEND_DIR=%ROOT_DIR%\src\updater\gui\frontend
set OUTPUT_DIR=%ROOT_DIR%\dist
set DIST_FOLDER=%OUTPUT_DIR%\updater_gui.dist
set ZIP_FILE=%OUTPUT_DIR%\updater_gui.zip

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

echo.
echo Building frontend...
cd "%FRONTEND_DIR%"
call npm run build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Frontend build failed.
    pause
    exit /b 1
)
cd "%ROOT_DIR%"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo Updating version from pyproject.toml...
"%VENV_PYTHON%" "%ROOT_DIR%\scripts\update_version.py"

echo.
echo Building updater_gui.exe with Nuitka...
echo Source : %SOURCE_FILE%
echo Output : %OUTPUT_DIR%\updater_gui.exe
echo.

"%VENV_PYTHON%" -m nuitka ^
    --standalone ^
    --mingw64 ^
    --output-filename=updater_gui.exe ^
    --output-dir="%OUTPUT_DIR%" ^
    --include-data-dir="%FRONTEND_DIR%\dist"=frontend/dist ^
    --include-module=webview ^
    --include-module=webview.platforms ^
    --include-module=webview.platforms.winforms ^
    --nofollow-import-to=webview.platforms.android ^
    --nofollow-import-to=webview.platforms.gtk ^
    --nofollow-import-to=webview.platforms.cocoa ^
    --nofollow-import-to=webview.platforms.qt ^
    --disable-plugin=pywebview ^
    --include-package=packaging ^
    --windows-console-mode=disable ^
    --assume-yes-for-downloads ^
    "%SOURCE_FILE%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo Renaming output folder...
if exist "%DIST_FOLDER%" rmdir /s /q "%DIST_FOLDER%"
move "%OUTPUT_DIR%\app.dist" "%DIST_FOLDER%"

echo Packaging zip for distribution...
if exist "%ZIP_FILE%" del "%ZIP_FILE%"
powershell -Command "Compress-Archive -Path '%DIST_FOLDER%' -DestinationPath '%ZIP_FILE%' -Force"

echo.
echo Build successful: %ZIP_FILE%
echo Standalone folder: %DIST_FOLDER%
