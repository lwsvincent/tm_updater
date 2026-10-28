@echo off
setlocal

rem Builds the GUI updater twice:
rem   1) onedir  (dist\updater_gui.dist)  - folder, fastest start
rem   2) onefile (dist\onefile)           - single portable exe
rem The onefile build uses AV-friendly settings (MSVC toolchain, full version
rem metadata, stable cached unpack dir, no self-extractor compression).
rem Keep the onedir build as the fallback when a site blocks single-file exes.

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe
set SOURCE_FILE=%ROOT_DIR%\src\updater\gui\app.py
set FRONTEND_DIR=%ROOT_DIR%\src\updater\gui\frontend
set OUTPUT_DIR=%ROOT_DIR%\dist
set DIST_FOLDER=%OUTPUT_DIR%\updater_gui.dist
set ZIP_FILE=%OUTPUT_DIR%\updater_gui.zip
set ONEFILE_DIR=%OUTPUT_DIR%\onefile
rem Separate Nuitka output dirs: both builds would otherwise share "app.dist"
rem (named after app.py) and the second build would overwrite the first.
set ONEDIR_OUT=%OUTPUT_DIR%\onedir_build
set ONEFILE_OUT=%OUTPUT_DIR%\onefile_build
set VERSION_FILE=%OUTPUT_DIR%\tm_version.txt

set COMPANY_NAME=Test Matrix
set PRODUCT_NAME=Test Matrix Updater

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

rem Version is read from a file: "for /f ('"exe" "arg"')" loses the quotes and
rem silently yields nothing, which used to stamp the exe as 0.0.0.0.
set TM_VER=
"%VENV_PYTHON%" "%ROOT_DIR%\scripts\print_version.py" > "%VERSION_FILE%" 2>nul
set /p TM_VER=<"%VERSION_FILE%"
if "%TM_VER%"=="" set TM_VER=0.0.0
echo Version for exe metadata: %TM_VER%

if exist "%ONEDIR_OUT%" rmdir /s /q "%ONEDIR_OUT%"
if exist "%ONEFILE_OUT%" rmdir /s /q "%ONEFILE_OUT%"

rem No --mingw64: MSVC is used when available (nicer, normally linked binary),
rem Nuitka falls back to MinGW64 automatically otherwise.
set COMMON_FLAGS=--standalone ^
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
    --company-name="%COMPANY_NAME%" ^
    --product-name="%PRODUCT_NAME%" ^
    --product-version=%TM_VER% ^
    --file-version=%TM_VER% ^
    --file-description="Test Matrix package updater" ^
    --copyright="Copyright Test Matrix Team" ^
    --assume-yes-for-downloads

echo.
echo [1/2] Building onedir updater_gui.exe ...
"%VENV_PYTHON%" -m nuitka %COMMON_FLAGS% ^
    --output-dir="%ONEDIR_OUT%" ^
    --report="%OUTPUT_DIR%\build_report_onedir.txt" ^
    --output-filename=updater_gui.exe ^
    "%SOURCE_FILE%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] onedir build failed.
    pause
    exit /b 1
)

rem Nuitka names the dist folder after the main module (app.dist).
if not exist "%ONEDIR_OUT%\app.dist" (
    echo.
    echo [ERROR] onedir output not found: %ONEDIR_OUT%\app.dist
    pause
    exit /b 1
)
if exist "%DIST_FOLDER%" rmdir /s /q "%DIST_FOLDER%"
move "%ONEDIR_OUT%\app.dist" "%DIST_FOLDER%"
if not exist "%DIST_FOLDER%\updater_gui.exe" (
    echo.
    echo [ERROR] missing %DIST_FOLDER%\updater_gui.exe after rename.
    pause
    exit /b 1
)

echo Packaging zip for distribution...
if exist "%ZIP_FILE%" del "%ZIP_FILE%"
powershell -NoProfile -Command "Compress-Archive -Path '%DIST_FOLDER%' -DestinationPath '%ZIP_FILE%' -Force"
if not exist "%ZIP_FILE%" (
    echo.
    echo [ERROR] failed to create %ZIP_FILE%
    pause
    exit /b 1
)

echo.
echo [2/2] Building onefile updater_gui.exe ...
"%VENV_PYTHON%" -m nuitka %COMMON_FLAGS% ^
    --output-dir="%ONEFILE_OUT%" ^
    --report="%OUTPUT_DIR%\build_report_onefile.txt" ^
    --onefile ^
    --output-filename=updater_gui.exe ^
    --onefile-tempdir-spec="{CACHE_DIR}/{COMPANY}/{PRODUCT}/{VERSION}" ^
    --onefile-cache-mode=cached ^
    --onefile-no-compression ^
    "%SOURCE_FILE%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] onefile build failed.
    pause
    exit /b 1
)
if not exist "%ONEFILE_OUT%\updater_gui.exe" (
    echo.
    echo [ERROR] onefile output not found: %ONEFILE_OUT%\updater_gui.exe
    pause
    exit /b 1
)
if exist "%ONEFILE_DIR%" rmdir /s /q "%ONEFILE_DIR%"
mkdir "%ONEFILE_DIR%"
move /y "%ONEFILE_OUT%\updater_gui.exe" "%ONEFILE_DIR%\updater_gui.exe"

echo.
echo Build successful.
echo   onedir  : %DIST_FOLDER%   (zip: %ZIP_FILE%)
echo   onefile : %ONEFILE_DIR%\updater_gui.exe
echo   report  : %OUTPUT_DIR%\build_report_onedir.txt / build_report_onefile.txt
