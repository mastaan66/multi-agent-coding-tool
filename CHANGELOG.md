# Changelog

All notable project changes are documented here. The format follows Keep a
Changelog, and the project uses semantic versioning.

## Unreleased

### Added

- Standalone PyInstaller executable builds for Linux, macOS, and Windows.
- Checksum-verifying Linux/macOS installer.
- Source-checkout shell launcher.
- GitHub release workflow with cross-platform artifacts.
- Reproducible SVG, GIF, and MP4 documentation media.
- Community health files and issue templates.

## 0.2.0 - 2026-06-27

### Added

- Typed pipeline and unsafe-path errors.
- Deterministic offline demo coverage.
- Pytest, Ruff, mypy, and Python 3.10/3.12 CI.
- Product and engineering roadmap.

### Changed

- Centralized real and mock stage execution.
- Isolated generated test runs in temporary directories.
- Validated all generated paths before writing.
- Corrected demo project imports and multiline artifacts.

### Fixed

- The broken --output-dir CLI override.
- Mock responses shifting when optional stages were skipped.
- Embedded Markdown fences corrupting otherwise valid JSON.
- Misleading sandbox terminology for the bounded subprocess runner.
