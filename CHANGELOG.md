# Changelog

All notable changes to the Updater microservice will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/testmatrix/test-matrix/compare/updater-1.0.0...HEAD
[1.0.0]: https://github.com/testmatrix/test-matrix/releases/tag/updater-1.0.0
