# Changelog

All notable changes to the Updater microservice will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.0] - 2026-04-23

### Added
- Version downgrade capability: Users can now select and install older package versions via a dropdown selector in the GUI
- Modal confirmation dialog to prevent accidental downgrades
- Session-level auto-update disabling: When an older version is installed, auto-update is disabled for the current session to prevent overwrites
- Version selection dropdown: Replace static "Available: X.Y.Z" text with interactive dropdown showing all available versions sorted newest-first
- Comprehensive integration tests for version selection and downgrade workflows

### Changed
- PackageTable now displays version selector as dropdown instead of static text
- install_updates() function enhanced to support target_version parameter for versioned installations
- API response includes all available versions for each package

### Fixed
- Auto-update now respects session-level disable flag to prevent version overwrites after manual downgrades

## [1.2.0] - 2026-04-23

### Added
- Vue-based GUI with PyWebView bridge for package management
- Auto-update flow with config-driven initialization
- GUI launcher executable built with Nuitka
- Scan/update separation with concurrent execution
- Post-update executable launcher with mode evaluation
- Comprehensive test suite for CLI, config, core, launcher, and GUI components
- Relocated documentation files to docs/ directory

### Changed
- Refactored main.py as thin CLI wrapper using core, config, and launcher modules
- Enhanced status constants extraction for cleaner code organization

### Fixed
- Resolved code review issues including pipe deadlock and cache staleness

## [1.1.0] - 2026-04-22

### Added
- `updater.toml` configuration file to externalize `DEFAULT_SOURCE` and `MANAGED_PACKAGES`
- Config is loaded from next to the exe; built-in defaults apply when file is absent

## [1.0.0] - 2026-04-22

### Added
- Initial release of Updater microservice
- Standalone exe compiled with Nuitka
- Parallel scanning of wheel files for performance
- Batch version checking via pip list
- Support for dry-run mode
- Package-level independent versioning and deployment
- Microservice architecture with own venv and dependencies

### Changed
- Migrated updater.py from test_matrix root to independent Updater sub-project

[Unreleased]: https://github.com/testmatrix/test-matrix/compare/updater-1.3.0...HEAD
[1.3.0]: https://github.com/testmatrix/test-matrix/compare/updater-1.2.0...updater-1.3.0
[1.2.0]: https://github.com/testmatrix/test-matrix/compare/updater-1.1.0...updater-1.2.0
[1.1.0]: https://github.com/testmatrix/test-matrix/compare/updater-1.0.0...updater-1.1.0
[1.0.0]: https://github.com/testmatrix/test-matrix/releases/tag/updater-1.0.0
