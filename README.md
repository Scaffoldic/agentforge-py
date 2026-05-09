# agentforge-py

Python implementation of [AgentForge](https://github.com/Scaffoldic/agentforge-py)
— an open-source, plug-and-play framework for building production AI agents.

> **Status:** v0.0 — pre-alpha. feat-001 (core contracts & `Agent`
> orchestrator) is shipped; the rest of the v0.1 milestone is in
> progress. See `CHANGELOG.md` for what's landed.

## What is AgentForge

AgentForge is a framework for building AI agents in three lines plus
one `pip install`. The opinionated parts — cost guardrails, run-id
propagation, distributed tracing, fallback chains, durable claim
records, evaluator suites, prompt-injection and PII defenses by
default — are wired before you write a line of code. The interesting
parts — your tools, your prompts, your reasoning shape — are where you
spend your time.

```python
# Bedrock provider (feat-003) is the first concrete LLMClient.
# The provider package registers itself at import time.
from agentforge import Agent

async with Agent(
    model="bedrock:us.anthropic.claude-haiku-4-5-20251001-v1:0",
    strategy="react",
) as agent:
    result = await agent.run("Summarise this PR")
    print(result.output)
```

Credentials follow the standard AWS chain (`~/.aws/credentials`,
`AWS_PROFILE`, IAM role). Cross-region inference profile IDs
(`us.…`, `eu.…`, `apac.…`, `global.…`) are passed through to
Bedrock unchanged.

## Repository structure

This is a **uv workspace** — one git repo, multiple installable
packages managed in lock-step.

```
agentforge-py/
├── pyproject.toml                  workspace root + shared tool config
├── uv.lock                         shared lock file
├── packages/
│   ├── agentforge-core/            stable contracts (ABCs, value types)
│   ├── agentforge/                 default runtime (Agent, defaults)
│   └── agentforge-bedrock/         AWS Bedrock provider (LLM + embeddings)
├── tests/                          cross-package integration / conformance
└── .github/workflows/              CI
```

Packages publish to PyPI as separate distributions; users
`pip install agentforge` (or `agentforge[anthropic]` etc. as
provider modules ship) and the right pieces land in the venv.

## Install (end users)

```bash
pip install agentforge
```

Note: provider modules (`agentforge-anthropic`, `agentforge-bedrock`,
`agentforge-openai`, …) and persistence modules
(`agentforge-memory-sqlite`, `-postgres`, …) ship as separate packages
in the v0.1 milestone. Install only what you need.

## Development

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:Scaffoldic/agentforge-py.git
cd agentforge-py
uv sync --group dev                  # venv + members + dev deps
uv run pytest                        # all tests (unit + integration + conformance)
uv run ruff check                    # lint
uv run ruff format                   # auto-format
uv run mypy --strict packages/agentforge-core/src packages/agentforge/src
uv run pre-commit install            # git hooks
```

## Roadmap

What's planned but not yet shipped lives in
[`docs/roadmap.md`](./docs/roadmap.md). At time of writing, the
in-flight features are **feat-008** (`agentforge-memory-postgres`
for production persistence) and **feat-009** (`GraphStore` ABC plus
SurrealDB and Neo4j drivers — knowledge graphs and multi-hop
reasoning). The roadmap also tracks deferred items (Anthropic-
direct provider, entry-point auto-loader, GraphRAG, hybrid search).

## Contributing

Before you start: read [`AGENTS.md`](./AGENTS.md) for the repo
conventions (uv workspace layout, locked contract layer, anti-patterns
reviewers will reject, the pre-commit gate, how to add a new module
package).

Branch and PR conventions:

- Branch from `main`. Names: `feat/<NNN>-<slug>`, `fix/<slug>`,
  `docs/<slug>`, `chore/<slug>`.
- Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`,
  `refactor:`, `chore:`, `perf:`, `revert:`.
- One feature = one PR. Squash-merge to `main`.
- 90% coverage gate; pre-commit + CI block below.

## License

Apache 2.0. See [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).
