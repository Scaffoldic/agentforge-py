# Changelog

All notable changes to `agentforge-py` are documented here. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The framework follows a coordinated release train (per ADR-0015): every
release tag bumps every workspace member to the same minor version.

## [Unreleased]

### Added

- Repository bootstrap: uv workspace, ruff/mypy/pytest/coverage tooling,
  GitHub Actions CI, pre-commit hook, Apache 2.0 license, AGENTS.md,
  README, member package skeletons (`agentforge-core`, `agentforge`).
- **feat-001 (in progress)** — production-rails primitives and value
  types in `agentforge-core`:
  - `BudgetPolicy` with USD / token / iteration / error-streak caps and
    reserve / commit / release semantics (per ADR-0010).
  - `RunContext` + `current_run()` ContextVar + `RunIdFilter` for
    structured-logging correlation across async tasks.
  - Full exception hierarchy: `AgentForgeError` + `BudgetExceeded`,
    `GuardrailViolation`, `ModuleError`, `ProviderError`,
    `CapabilityNotSupported`.
  - Frozen Pydantic v2 value types: `Message`, `ToolCall`, `ToolSpec`,
    `TokenUsage`, `LLMResponse`, `Step`, `AgentState`, `RunResult`,
    `Claim`.
  - 100 unit tests + 1 Hypothesis property test; 99.22% coverage.

### Fixed

- Repository placeholder URLs replaced with the live remote
  (`github.com/Scaffoldic/agentforge-py`).
- Workspace `pyproject.toml` migrated from deprecated
  `[tool.uv] dev-dependencies` to `[dependency-groups] dev`; root
  declares workspace members as dependencies so `uv sync` installs
  them into the shared venv.

[Unreleased]: https://github.com/Scaffoldic/agentforge-py/compare/HEAD...HEAD
