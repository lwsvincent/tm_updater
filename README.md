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
updater.exe [--source <path>] [--venv <path>] [--packages pkg1 pkg2 ...] [--dry-run]
```

### Arguments

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
```

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
# Run build script
scripts\build_updater.bat

# Output: dist\updater.exe
```

### Testing

```bash
# Run pytest
pytest

# Dry-run test (requires network access to PNT52)
dist\updater.exe --dry-run
```

## Architecture

- `src/updater/main.py` — Core updater logic
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
