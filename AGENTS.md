# AGENTS.md — agentforge-py

> Repository conventions for any AI assistant editing this repo.
> Tool-agnostic — `CLAUDE.md` and any future tool-specific rules files
> defer to this one.

## What this repo is

`agentforge-py` is the Python implementation of [AgentForge](https://github.com/Scaffoldic/agentforge-py),
an open-source plug-and-play framework for building production AI
agents. The repo is a **uv workspace** with two member packages today:

- `packages/agentforge-core/` — locked contracts (ABCs, value types,
  production-rails primitives, resolver, testing utilities). No I/O,
  no third-party SDKs except Pydantic + python-ulid.
- `packages/agentforge/` — default runtime (`Agent` orchestrator,
  `InMemoryStore`, configuration loader). Imports from
  `agentforge-core`; never the reverse.

When new modules ship (provider clients, persistence drivers, MCP,
observability, safety, etc. — see `CHANGELOG.md`), each lands as a
new directory under `packages/`. The workspace glob in the root
`pyproject.toml` already covers them.

## Hard rules

| # | Rule | Reference |
|---|---|---|
| 1 | `agentforge-core` imports nothing from `agentforge` or any other module package. It is the leaf of the dependency graph. | dependency policy |
| 2 | Contracts in `agentforge-core` (every ABC + the `Finding` Protocol + the locked value types) are **stable surface**. Adding a method to an ABC is a major version bump; adding a field with a safe default is a minor bump. | locked contract layer |
| 3 | Configuration is data, not code. No dynamic imports from YAML; no Jinja inside config. Env-var interpolation only (`${VAR}`, `${VAR:default}`, `${VAR:?error}`, `$$` → `$`). | `agentforge.config` |
| 4 | No magic numbers in production code. Every threshold / timeout / limit comes from a Pydantic config model with a documented default. | configuration policy |
| 5 | Test coverage must be ≥ 90% on every commit. Pre-commit blocks below; CI ratchet rejects regressions on `main`. | `.pre-commit-config.yaml` + `.github/workflows/ci.yml` |
| 6 | One feature = one branch = one PR. Conventional Commits format (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `perf:`, `revert:`). | PR template |
| 7 | Never bypass pre-commit with `--no-verify` unless the user explicitly authorises it for a specific commit (and the bypass is documented in the commit message). | pre-commit policy |
| 8 | Type hints everywhere. `mypy --strict` is the gate. `Any` only at genuine boundaries (raw provider responses); never to paper over untyped internals. | `pyproject.toml > [tool.mypy]` |
| 9 | Async-first. Public methods on locked contracts are `async def`. Sync callers use the `*_sync` shims (where exposed) or `asyncio.run()`. | locked contract layer |

## Anti-patterns reviewers will reject

- **`from langchain... import`** anywhere. Wrong framework.
- **Hand-written JSON schemas** for tools — use Pydantic models on the
  `Tool` ABC's `input_schema` class attribute (or the `@tool`
  decorator once feat-004 ships).
- **API keys as YAML literals** — use `${ENV_VAR}`.
- **Catching exceptions to "make robust"** — let them surface; the
  framework records them as observations and the LLM recovers.
- **Wrappers around `Agent.run()` to add cross-cutting features** —
  use the hook system (`on_step` / `on_finish`) once feat-009 ships
  observability backends.
- **Module-level singleton config** (`dspy.configure(...)` style) —
  use dependency injection.
- **Threading for I/O** — use `asyncio`.

## Workflow

- Branch from `main`. Conventional branch names: `feat/<NNN>-<slug>`,
  `fix/<slug>`, `docs/<slug>`, `chore/<slug>`. **`<NNN>` must match
  the canonical feature number** in
  `/Users/khemchandjoshi/MbytesWorkspace/ai-agents/docs/features/feat-NNN-*.md`.
  If you can't find a canonical spec for the work, the work doesn't
  have a feat-NNN number — use a `chore/` or `docs/` branch instead,
  or write a spec first.
- **Every feature PR updates the matching canonical spec's
  Implementation section** — what shipped, what was deferred, any
  deviations from the original design, link to the PR. The spec is
  the durable record; CHANGELOG is the user-facing summary. Both
  ship in the same PR.
- Every commit goes through pre-commit (`pre-commit install` after a
  fresh clone). The hook runs ruff / mypy / bandit / pytest /
  coverage. Failures block.
- One feature = one PR. Squash-merge to `main`.
- CI runs the same checks plus a multi-OS test matrix (Linux, macOS,
  Windows) on Python 3.13.

## How to add a new module package

1. Create `packages/agentforge-<X>/` with the structure used by
   existing members (`pyproject.toml`, `src/agentforge_<x>/`,
   `tests/unit/`).
2. Declare entry points in the new `pyproject.toml` under
   `[project.entry-points."agentforge.<category>"]`.
3. Pin against `agentforge-core ~= <current major>`.
4. Add at least one test.
5. If the module belongs to a curated extra (`[anthropic]`, `[full]`,
   etc.), update `packages/agentforge/pyproject.toml`'s
   `[project.optional-dependencies]`.

## Pre-commit (local)

```bash
uv sync --group dev
uv run pre-commit install
```

The hook runs:

- `ruff format` (pinned to `v0.15.12` — matches the venv and CI)
- `ruff check --fix`
- `mypy --strict` on `packages/*/src/`
- `bandit -c pyproject.toml -r packages/*/src/`
- `pytest -q -x -m "not live"` (per-package + workspace tests)
- `pytest --cov --cov-fail-under=90`

## Reading order on a fresh clone

1. This file.
2. `README.md` — quickstart, repo layout, install + dev commands.
3. `CHANGELOG.md` — what's shipped and what's coming.
4. `packages/agentforge-core/src/agentforge_core/` — the locked
   contract layer. Start with `contracts/` then `values/` then
   `production/`.
5. `packages/agentforge/src/agentforge/agent.py` — the orchestrator
   that ties everything together.

<!-- agentforge:custom -->
<!-- Project-specific instructions go below this line. Survives upgrades. -->
<!-- agentforge:end-custom -->
