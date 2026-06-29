# Changelog

All notable project changes are documented here. The format follows Keep a
Changelog, and the project uses semantic versioning.

## Unreleased

### Added

- Token-bounded context compilation that preserves atomic assistant/tool-call blocks.
- Runtime context accounting and provider usage aggregation.
- SQLite-backed sessions, append-only runtime events, and structured task ledgers.
- Verification evidence requirements before ledger tasks can be completed.
- Content-addressed artifact storage and bounded model projections for large tool output.
- Continuity architecture and v0.5.0 release gates.
- Normalized message persistence and provider-safe interrupted tool-call replay.
- Persistent agent sessions that resume conversation history and global turn numbering.
- Durable ORIENT-to-HANDOFF harness state with append-only transition history.
- Atomic task/phase/session updates and schema-versioned SQLite migrations.
- Restart-level replay, resume, and lifecycle integration coverage.

### Changed

- Tool results now carry explicit model-content, artifact, and truncation metadata.

## 0.3.0 - 2026-06-28

### Added

- Read-only `ai-factory inspect` output in text and JSON formats.
- Git-aware repository discovery with file limits and symlink containment.
- Hierarchical `AGENTS.md` instruction loading.
- Provider-neutral model events, tool contracts, registry, and bounded runtime.
- Validated file reading, text search, Git status, and Git diff tools.
- Repeated tool-call loop detection and runtime lifecycle events.

### Changed

- Exposed the existing project generator through `ai-factory generate` while
  preserving direct-prompt compatibility.
- Expanded tests and mypy coverage for repository and runtime components.

### Fixed

- CI now invokes pytest through `python -m pytest` so repository modules resolve
  consistently after editable installs.

## 0.2.0 - 2026-06-27

### Added

- Standalone PyInstaller executable builds for Linux, macOS, and Windows.
- Checksum-verifying Linux/macOS installer.
- Source-checkout shell launcher.
- GitHub release workflow with cross-platform artifacts.
- Reproducible SVG, GIF, and MP4 documentation media.
- Community health files and issue templates.
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
