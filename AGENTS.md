# AGENTS.md — agentforge-py

> Scoped AI rules for the **`agentforge-py`** repository specifically.
> The project-wide canonical rules live at
> [`../../AGENTS.md`](../../AGENTS.md). Read both.

## Read first

1. [`../../AGENTS.md`](../../AGENTS.md) — project-wide rules and the
   12 hard rules (every change must honour at least one design
   principle, locked contracts, configuration-driven, etc.)
2. [`../../.claude/state/current.md`](../../.claude/state/current.md)
   — what feature is in progress, on which branch
3. [`../../.claude/development-pipeline.md`](../../.claude/development-pipeline.md)
   — per-feature workflow

## Repo-specific shape

This is a **uv workspace** with two member packages today:

- `packages/agentforge-core/` — locked ABCs and value types. No I/O,
  no third-party SDKs except Pydantic.
- `packages/agentforge/` — the default runtime. Imports from
  `agentforge-core`; never the reverse.

When a feature adds a new module (e.g. `agentforge-anthropic`,
`agentforge-memory-postgres`), it lands as a new directory under
`packages/`. The new member is added to the `[tool.uv.workspace] members`
glob in the root `pyproject.toml` (already a wildcard, no edit needed).

## Hard rules specific to this repo

- **`agentforge-core` imports nothing from `agentforge` or any other
  module.** It's the leaf of the dependency graph.
- **No magic numbers** — every threshold/timeout/limit comes from a
  Pydantic config model with a documented default. See
  [`../../.claude/standards/configuration.md`](../../.claude/standards/configuration.md).
- **Type hints everywhere** — `mypy --strict` is the gate.
  `Any` only at genuine boundaries (raw provider responses).
- **Async by default** — public methods on contracts are `async def`.
  Sync wrappers only as explicit `*_sync` shims.
- **No print statements** — use `logging.getLogger(__name__)`.
- **No `from langchain... import`** anywhere. Wrong framework.
- **Tests use fixtures from YAML** under `tests/fixtures/`. Never
  inline test data.

## Pre-commit

Install with `pre-commit install`. The hook config at
[`.pre-commit-config.yaml`](./.pre-commit-config.yaml) enforces:

- `ruff format` + `ruff check --fix`
- `mypy --strict`
- `bandit -q -r packages/*/src/`
- `pytest tests/unit -q -x` (and per-package unit tests)
- `pytest tests/integration -q -x -m "not live"`
- `pytest --cov --cov-fail-under=90`

Failure blocks the commit. Never bypass with `--no-verify` unless the
user explicitly authorises.

## Anti-patterns to avoid (will be flagged by reviewers and AI)

- LangChain idioms (`Runnable`, `LCEL`, `RunnablePassthrough`)
- Hand-written JSON schemas — use Pydantic and the `@tool` decorator
- API keys as YAML literals — use `${ENV_VAR}`
- Catching exceptions to "make robust" — let them surface
- Wrappers around `Agent.run()` to add cross-cutting features — use hooks
- Module-level singleton config (`dspy.configure(...)` style) — use DI
- Threading for I/O — use `asyncio`

## How to add a new module package

1. Create `packages/agentforge-<X>/` with the same structure as
   existing members (`pyproject.toml`, `src/agentforge_<x>/`, `tests/`).
2. Declare entry points in the new `pyproject.toml` under
   `[project.entry-points."agentforge.<category>"]`.
3. Pin against `agentforge-core ~= <current major>`.
4. Add at least one test in the new `tests/` directory.
5. Update the workspace's `agentforge` aggregate optional-dependencies
   in `packages/agentforge/pyproject.toml` if the new module belongs to
   a curated extra (`[anthropic]`, `[full]`, etc.).

<!-- agentforge:custom -->
<!-- Project-specific instructions go below this line. Survives upgrades. -->
<!-- agentforge:end-custom -->
