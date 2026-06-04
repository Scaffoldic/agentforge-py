# Contributing to AgentForge

Thanks for your interest in AgentForge! It's an open-source, plug-and-play
framework for building production AI agents in Python. Contributions —
issues, docs, fixes, new modules — are very welcome.

This project is **self-contained**: every spec, standard, checklist, design
doc, and ADR lives inside this repo. You don't need to read anything outside
it to contribute.

By participating you agree to abide by our
[Code of Conduct](./CODE_OF_CONDUCT.md).

---

## TL;DR

```bash
# 1. Fork + clone, then set up the uv workspace
uv sync --all-extras --dev

# 2. Branch from main (see naming below)
git switch -c fix/short-slug main

# 3. Make your change with tests, then run the full gate
uv run pre-commit run --all-files

# 4. Push and open one PR (Conventional Commits title)
```

---

## Project layout

`agentforge-py` is a [uv](https://docs.astral.sh/uv/) workspace. The core
contracts live in `packages/agentforge-core/`; the default runtime in
`packages/agentforge/`; every provider, backend, guardrail, evaluator,
observability, and protocol module is its own package under `packages/`.

Read [`AGENTS.md`](./AGENTS.md) first — it's the canonical conventions doc
(hard rules, anti-patterns, branch/PR rules). The deeper material:

- `docs/features/` — canonical `feat-NNN` specs (the catalogue is
  `docs/features/README.md`).
- `docs/design/` and `docs/adr/` — architecture and immutable decision
  records.
- `.claude/standards/` — coding / testing / git / docs / configuration
  standards.
- `.claude/checklists/` — pre-feature / pre-commit / pre-pr / feature-complete.

## Prerequisites

- **Python 3.13** (the current baseline; `requires-python = ">=3.13"`).
- **uv** for environment + workspace management.

## Development setup

```bash
uv sync --all-extras --dev      # install everything incl. dev tooling
uv run pre-commit install       # install the git hook (recommended)
```

## The hard rules (most important ones)

These are enforced in review and CI. Full list in `AGENTS.md`.

1. **`agentforge-core` is the dependency leaf** — it imports nothing from
   `agentforge` or any other module package.
2. **Locked contracts are stable surface.** Adding an abstract method to a
   shipped ABC is a major version bump; adding a field with a safe default
   is a minor bump. (See ADR-0007.)
3. **Configuration is data, not code.** No dynamic imports from YAML, no
   Jinja in config; env-var interpolation only (`${VAR}`, `${VAR:default}`).
4. **No magic numbers** in production code — every threshold/timeout/limit
   comes from a documented Pydantic config default.
5. **Coverage ≥ 90%** on every commit (pre-commit blocks below it; CI
   rejects regressions on `main`).
6. **One feature = one branch = one PR**, Conventional Commits.
7. **Type hints everywhere**; `mypy --strict` is the gate. `Any` only at
   genuine boundaries.
8. **Async-first.** Public methods on locked contracts are `async def`.

### Anti-patterns reviewers will reject
- `from langchain... import` anything (wrong framework).
- Hand-written JSON tool schemas — use Pydantic models / the `@tool` decorator.
- API keys as YAML literals — use `${ENV_VAR}`.
- Catching exceptions just to "make robust" — let them surface; the framework
  records them as observations.
- Module-level singleton config — use dependency injection.
- Threads for I/O — use `asyncio`.

## Branch & PR conventions

- **Branch from `main`.** Names:
  - `feat/<NNN>-<slug>` — `<NNN>` **must** match a canonical
    `docs/features/feat-NNN-*.md` spec. No invented numbers.
  - `fix/<slug>`, `docs/<slug>`, `chore/<slug>` for everything else.
- **Conventional Commits** for titles: `feat:`, `fix:`, `docs:`, `test:`,
  `refactor:`, `chore:`, `perf:`, `revert:`.
- **One feature per PR**, squash-merged.
- **Every feature PR updates the matching spec's `Implementation status`**
  section in the same PR. The CHANGELOG is the user-facing summary; the spec
  is the developer-facing one.

## The pre-commit gate (run before every push)

```bash
uv run pre-commit run --all-files
```

This runs, in order: ruff format → ruff check → `mypy --strict` → bandit →
pytest (unit + integration) → coverage ≥ 90%. CI mirrors it exactly across
Linux / macOS / Windows, plus a live-integration job. A PR is mergeable only
when the whole gate is green.

> **Never** bypass with `git commit --no-verify` unless a maintainer
> explicitly authorises it for a specific commit (and you document the
> bypass in the commit message).

### Live tests
Live integration tests are env-gated (`-m live`) and are **not** part of the
local pre-commit run — they execute in CI's "Live" job against real services.
You generally don't need credentials to contribute; the standard gate runs
fully offline.

## Tests

- Put unit tests in the package's `tests/unit/`, integration in
  `tests/integration/`.
- Every backend driver must pass the shared **conformance harness** — if you
  add a new implementation of a contract, wire it into the conformance tests.
- See `.claude/standards/testing.md` for the full testing policy.

## Reporting bugs / requesting features

- **Bugs:** open an issue with a minimal reproduction, expected vs. actual,
  versions (Python, `agentforge-py`), and the relevant config/traceback.
- **Features:** describe the use case and the production problem it solves.
  Larger features may need a `feat-NNN` spec under `docs/features/` first —
  maintainers will guide you.
- Looking for somewhere to start? Check issues labeled `good first issue`
  and `help wanted`, and the backlog in `docs/roadmap.md`.

## Security

Please **do not** open public issues for security vulnerabilities. See
[`SECURITY.md`](./SECURITY.md) for private reporting.

## License

By contributing, you agree that your contributions will be licensed under
the project's [Apache-2.0 License](./LICENSE).
