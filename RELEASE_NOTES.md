# Release Notes - Updater v1.0.0

## Overview

The Updater microservice is now available as an independent sub-project within the Test Matrix workspace. This release marks the migration of the package updater from being embedded in test_matrix to a standalone microservice with its own venv, versioning, and build process.

## What's New

### Microservice Architecture
- Updater is now a standalone microservice with independent versioning
- Own virtual environment and dependencies (minimal: `packaging` only)
- Independent release cycle from test_matrix
- Compiled to standalone `.exe` using Nuitka (no Python runtime required)

### Performance Improvements
- Parallel wheel file scanning for faster source directory scans
- Batch pip queries reduce version check time significantly

### Features
- **Dry-run mode:** Preview all updates before installation
- **Package selection:** Update specific packages or all managed packages
- **Custom venv support:** Specify alternative venv locations
- **Version comparison:** PEP 440 semantic versioning

## Installation & Usage

### Prerequisites
- Windows 10/11 with .NET runtime (Nuitka build)
- Python 3.11+ (for development)
- Network access to PNT52 share (default source)

### Quick Start

```bash
# Run updater with dry-run (preview only)
updater.exe --dry-run

# Install all available updates
updater.exe

# Update specific packages
updater.exe --packages test-matrix scope_driver
```

For detailed usage, see [README.md](README.md).

## Architecture Changes

**Before:** `test_matrix/updater.py` — embedded in main project
**After:** `Updater/` — independent sub-project
- Source code: `Updater/src/updater/main.py`
- Build output: `Updater/dist/updater.exe`
- Versioning: Independent (currently 1.0.0)

## Managed Packages

Updater automatically manages these packages:

```
test-matrix, scope_driver, source_driver, load_driver, meter_driver,
daq_driver, chamber_driver, gpio_driver, i2c_driver,
dc_power_supply_driver, multi_driver, subdevice, usb_hid, acbel_r90000,
am_shared, am_report_generator, visa_bundle
```

## Known Limitations

- Network share (`\\pnt52\...`) must be accessible for default operation
- Exe built via Nuitka (compilation takes 5-10 minutes)
- Windows only (due to Nuitka/mingw64 build dependency)

## Future Roadmap

- [ ] Automated version checking against network share
- [ ] GUI for easier package selection
- [ ] Configuration file support
- [ ] Integration with CI/CD pipeline
- [ ] Cross-platform support (Linux/macOS via different build)

## Support

For issues or questions:
- Email: testmatrix@example.com
- Repository: https://github.com/testmatrix/test-matrix

---

**Release Date:** 2026-04-22  
**Version:** 1.0.0  
**Build:** Nuitka standalone exe
