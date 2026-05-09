# agentforge-py

Python implementation of [AgentForge](https://github.com/) — an open-source,
plug-and-play framework for building production AI agents.

> **Status:** v0.0 — pre-alpha. The repo is bootstrapped; no features
> shipped yet. The full design lives in the design workspace at
> [`../docs/`](../docs/) (relative to the parent `ai-agents/` workspace).

## What is AgentForge

AgentForge is a framework for building AI agents in three lines plus one
`pip install`. The opinionated parts — cost guardrails, run-id propagation,
distributed tracing, fallback chains, durable claim records, evaluator
suites, prompt-injection and PII defenses by default — are wired before
you write a line of code. The interesting parts — your tools, your
prompts, your reasoning shape — are where you spend your time.

The full pitch and architecture are in the design workspace docs:

- [`../../docs/README.md`](../../docs/README.md) — entry point
- [`../../docs/design/architecture.md`](../../docs/design/architecture.md) — system view
- [`../../docs/features/README.md`](../../docs/features/README.md) — feature catalogue
- [`../../docs/adr/README.md`](../../docs/adr/README.md) — decision records

## Repository structure

This is a **uv workspace** — one git repo, multiple installable packages
managed in lock-step (per ADR-0003 + ADR-0015).

```
agentforge-py/
├── pyproject.toml                  workspace root + shared tool config
├── uv.lock                         shared lock file
├── packages/
│   ├── agentforge-core/            stable contracts (ABCs, value types)
│   └── agentforge/                 default runtime (Agent, ReAct, defaults)
├── tests/                          cross-package integration / conformance
└── .github/workflows/              CI
```

Packages publish to PyPI as separate distributions; users `pip install
agentforge` (or `agentforge[anthropic]`) and the right pieces land.

## Development

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/).

```bash
uv sync                              # create venv, install all members + dev deps
uv run pytest                        # run all tests
uv run ruff check                    # lint
uv run mypy --strict packages/       # type-check
pre-commit install                   # install git hooks
```

## Contributing

This repo follows the AgentForge framework's strict development pipeline.
Before you start, read:

1. [`AGENTS.md`](./AGENTS.md) — repo-scoped AI assistant rules
2. [`../../AGENTS.md`](../../AGENTS.md) — project-wide rules
3. [`../../.claude/development-pipeline.md`](../../.claude/development-pipeline.md) — per-feature workflow
4. [`../../.claude/standards/`](../../.claude/standards/) — coding, testing, docs, git, configuration

## License

Apache 2.0. See [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).
