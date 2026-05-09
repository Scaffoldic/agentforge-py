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

- **feat-001 — Core contracts & `Agent` orchestrator.** The
  foundational layer of AgentForge.

  *agentforge-core (Tier 1):*
  - **Locked contracts (ABCs + Protocol):** `LLMClient`, `Tool`,
    `ReasoningStrategy`, `MemoryStore`, `Evaluator` ABCs plus the
    `Finding` Protocol. Adding a method to any of these is a major
    version bump (per ADR-0007).
  - **Locked value types (frozen Pydantic v2):** `Message`,
    `ToolCall`, `ToolSpec`, `TokenUsage`, `LLMResponse`, `Step`,
    `AgentState`, `RunResult`, `Claim`, `EvalResult`. Closed
    `Literal` enums for `MessageRole`, `StopReason`, `StepKind`,
    `FinishReason`. ULID-defaulted `Claim.id` and run ids.
  - **Production rails:** `BudgetPolicy` (USD / token / iteration /
    error-streak caps with `reserve` / `commit` / `release_reservation`
    semantics), `RunContext` + `current_run()` ContextVar +
    `bind_run` / `reset_run` lifecycle, `RunIdFilter` (idempotent
    install / uninstall) for stdlib-logging correlation, full
    exception hierarchy.
  - **Resolver:** in-process module registry (`Resolver`,
    `@register` decorator) and `parse_model_string` for the
    `<provider>:<model_id>` syntax.
  - **Testing utilities:** `agentforge_core.testing.run_memory_conformance`
    — the shared conformance suite every memory driver must pass.

  *agentforge (Tier 2 — default runtime):*
  - **`Agent` orchestrator** with the locked constructor surface
    per feat-001 §4.2 and the lifecycle defined in ADR-0010
    (bind run_id → strategy.run → fire on_finish → produce
    RunResult). Async context manager.
  - **`InMemoryStore`** — process-local `MemoryStore` reference impl
    used by default when no persistence module is configured.
  - **Configuration loader** with env-var interpolation
    (`${VAR}`, `${VAR:default}`, `${VAR:?error}`, `$$` → `$`),
    Pydantic schema validation, and `extra="forbid"` rejection of
    unknown sections (per ADR-0013).

  *Tests:* 192 unit + integration + conformance + Hypothesis
  property tests. 94.28% line + branch coverage on the diff.

### Fixed

- Repository placeholder URLs replaced with the live remote
  (`github.com/Scaffoldic/agentforge-py`).
- Workspace `pyproject.toml` migrated from deprecated
  `[tool.uv] dev-dependencies` to `[dependency-groups] dev`; root
  declares workspace members as dependencies so `uv sync` installs
  them into the shared venv.
- Pre-commit `bandit` hook now passes `-c pyproject.toml` so it
  reads `[tool.bandit]` (skips B101 — assert is the legitimate
  conformance-suite mechanism).

[Unreleased]: https://github.com/Scaffoldic/agentforge-py/compare/HEAD...HEAD
