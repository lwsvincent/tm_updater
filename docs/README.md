# Updater Microservice

A standalone package updater for Test Matrix microservices. Scans a network share for `.whl` wheel files and installs newer versions of packages into a Python virtual environment.

## Features

- Parallel scanning of wheel files for performance
- Version comparison using PEP 440 semantics
- Batch pip queries for faster version checking
- Dry-run mode for preview before installation
- Compiled to standalone `.exe` using Nuitka (no Python installation required on target)

## Usage

```bash
updater.exe [--project <folder>] [--source <path>] [--venv <path>] [--packages pkg1 pkg2 ...] [--dry-run]
```

### Arguments

- `--project <folder>` — **The folder to update** (its `venv\` and `updater.toml`). The exe itself may live anywhere. Without it, the nearest ancestor of the current directory that contains a venv or `updater.toml` is used, then the exe's own folder (legacy behaviour). See `docs/specs/target_resolution_spec.md`. The GUI takes the same flag and can also switch folders at runtime via the target bar.
- `--source <path>` — Path to directory containing `.whl` files (default: `\\pnt52\研發本部_技術服務處\技術服務處\DS-TA\Test_Matrix\packages`)
- `--venv <path>` — Path to Python virtual environment (auto-detected if not specified)
- `--packages pkg1 pkg2 ...` — Specific packages to update (default: all managed packages)
- `--dry-run` — Preview updates without installing
- `--debug` — Enable debug output

### Examples

```bash
# Check for updates without installing
updater.exe --dry-run

# Update only specific packages
updater.exe --packages test-matrix scope_driver

# Specify custom venv location
updater.exe --venv C:\project\.venv

# Dry-run with custom source
updater.exe --source D:\packages --dry-run

# One portable updater, several machines/projects
updater.exe --project D:\Work\TestMatrix --dry-run
updater_gui.exe --project D:\Work\TestMatrix
```

### updater.toml encoding

Save it as **UTF-8 without BOM**. Files saved as UTF-8 with BOM, UTF-16 or zh-TW
ANSI (Big5/cp950) are detected automatically; an unparseable file no longer aborts
the run — built-in defaults are used and the reason plus the detected encoding are
shown in the GUI (log + target bar) and on stderr. See `docs/specs/config_encoding_spec.md`.

## Development

### Prerequisites

- Python 3.11+
- Nuitka (for building exe)

### Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate and install dependencies
.venv\Scripts\activate.bat
pip install -e ".[dev]"
```

### Building

```bash
# CLI
scripts\build_updater.bat        # -> dist\updater.dist\updater.exe (+ updater.zip)

# GUI - builds both layouts
scripts\build_gui.bat            # -> dist\updater_gui.dist\  (onedir, + updater_gui.zip)
                                 # -> dist\onefile\updater_gui.exe (single file)
```

The onefile build is tuned to survive antivirus heuristics: MSVC instead of forced
MinGW64, full version-info metadata, a stable cached unpack directory
(`{CACHE_DIR}/{COMPANY}/{PRODUCT}/{VERSION}`) instead of a random `%TEMP%\onefile_*`,
and `--onefile-no-compression` (compressed self-extractors are what AV tends to flag).
If a site still blocks the single file, ship the onedir folder instead.

### Testing

```bash
# Run pytest
pytest

# Dry-run test (requires network access to PNT52)
dist\updater.exe --dry-run
```

## Architecture

- `src/updater/main.py` — CLI entry point
- `src/updater/target.py` — resolves *which folder* is being updated (project root, config, venv, source); pure functions, no global state
- `src/updater/config.py` — `updater.toml` loading incl. BOM / Big5 encoding recovery
- `src/updater/core.py` — scan / version compare / pip install
- `src/updater/gui/app.py` — pywebview bridge (`get_target`, `set_target`, `choose_target_folder`)
- `src/updater/__init__.py` — Package metadata
- `scripts/build_updater.bat` — Nuitka build automation
- `dist/updater.exe` — Compiled standalone executable

## Managed Packages

The updater manages the following packages by default:

- test-matrix
- scope_driver
- source_driver
- load_driver
- meter_driver
- daq_driver
- chamber_driver
- gpio_driver
- i2c_driver
- dc_power_supply_driver
- multi_driver
- subdevice
- usb_hid
- acbel_r90000
- am_shared
- am_report_generator
- visa_bundle

## License

MIT

## Support

For issues or questions, contact: testmatrix@example.com
