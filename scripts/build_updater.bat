@echo off
setlocal

rem CLI updater.  No --mingw64: MSVC is preferred when available (normally
rem linked binary, friendlier to antivirus), Nuitka falls back to MinGW64.

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe
set SOURCE_FILE=%ROOT_DIR%\src\updater\main.py
set OUTPUT_DIR=%ROOT_DIR%\dist
set DIST_FOLDER=%OUTPUT_DIR%\updater.dist
set ZIP_FILE=%OUTPUT_DIR%\updater.zip

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

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo Updating version from pyproject.toml...
"%VENV_PYTHON%" "%ROOT_DIR%\scripts\update_version.py"

rem Version is read from a file: "for /f ('"exe" "arg"')" loses the quotes and
rem silently yields nothing, which used to stamp the exe as 0.0.0.0.
set TM_VER=
"%VENV_PYTHON%" "%ROOT_DIR%\scripts\print_version.py" > "%OUTPUT_DIR%\tm_version.txt" 2>nul
set /p TM_VER=<"%OUTPUT_DIR%\tm_version.txt"
if "%TM_VER%"=="" set TM_VER=0.0.0
echo Version for exe metadata: %TM_VER%

echo.
echo Building updater.exe with Nuitka...
echo Source : %SOURCE_FILE%
echo Output : %OUTPUT_DIR%\updater.exe
echo.

"%VENV_PYTHON%" -m nuitka ^
    --standalone ^
    --disable-ccache ^
    --show-scons ^
    --jobs=1 ^
    --output-filename=updater.exe ^
    --output-dir="%OUTPUT_DIR%" ^
    --include-package=packaging ^
    --windows-console-mode=force ^
    --company-name="%COMPANY_NAME%" ^
    --product-name="%PRODUCT_NAME%" ^
    --product-version=%TM_VER% ^
    --file-version=%TM_VER% ^
    --file-description="Test Matrix package updater" ^
    --copyright="Copyright Test Matrix Team" ^
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
if not exist "%OUTPUT_DIR%\main.dist" (
    echo.
    echo [ERROR] Nuitka output not found: %OUTPUT_DIR%\main.dist
    pause
    exit /b 1
)
if exist "%DIST_FOLDER%" rmdir /s /q "%DIST_FOLDER%"
move "%OUTPUT_DIR%\main.dist" "%DIST_FOLDER%"
if not exist "%DIST_FOLDER%\updater.exe" (
    echo.
    echo [ERROR] missing %DIST_FOLDER%\updater.exe after rename.
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
echo Build successful: %ZIP_FILE%
echo Standalone folder: %DIST_FOLDER%
