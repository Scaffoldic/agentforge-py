# AgentForge

**Production AI agents in three lines of Python — with cost
guardrails, observability, safety, and your AI coding assistant
already on board.**

[![Latest release](https://img.shields.io/github/v/release/Scaffoldic/agentforge-py?label=release)](https://github.com/Scaffoldic/agentforge-py/releases)
[![License](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](#install)

> **Status:** `v0.2.0` shipped — 34 packages in tree, every locked
> ABC has at least one driver, 5 LLM providers + 4 reranker
> vendors + 4 observability backends + 4 vector stores + chat +
> MCP + A2A all coordinated. See
> [`docs/releases/v0.2.0.md`](./docs/releases/v0.2.0.md).

---

## Why AgentForge

The boring-but-load-bearing parts of an agent — cost limits,
run-id propagation, distributed tracing, fallback chains,
durable claim records, evaluator suites, prompt-injection and PII
defenses — are wired before you write a line of code. You spend
your time on **what your agent does**, not on plumbing.

```python
from agentforge import Agent

async with Agent(model="anthropic:claude-sonnet-4-7") as agent:
    result = await agent.run("Summarise this PR in three bullets.")
    print(result.output)
```

Swap the string-id (`anthropic:`, `openai:`, `bedrock:`,
`ollama:`, `litellm:`) and the same code routes to a different
provider. No caller changes.

---

## Quick start

```bash
pip install "agentforge-py[anthropic]"   # or [openai], [bedrock], [ollama], …
agentforge new my-agent --template minimal
cd my-agent

# Set the API key for the provider you picked
export ANTHROPIC_API_KEY=sk-ant-…

agentforge run "Hi"
```

Six starter templates ship in the wheel: `minimal`,
`code-reviewer`, `patch-bot`, `docs-qa`, `triage`, `research`.

---

## AI-assisted development: how it works

This is the part most agent frameworks miss. AgentForge ships
**framework-aware instructions for every major AI coding
assistant** inside every scaffolded agent — so the AI helping
you build your agent follows AgentForge's idioms automatically,
without you having to teach it.

```
my-agent/
├── AGENTS.md                            # canonical (Aider, Codex, Windsurf, …)
├── CLAUDE.md                            # → AGENTS.md pointer for Claude Code
├── .cursorrules                         # → AGENTS.md pointer for Cursor
├── .github/copilot-instructions.md      # → AGENTS.md pointer for GitHub Copilot
├── docs/runbooks/                       # 21 step-by-step "how to add X" guides
│   ├── 01-set-up-new-agent.md
│   ├── 02-add-a-tool.md
│   ├── …
│   └── 21-use-streaming-guardrails.md
├── agentforge.yaml                      # your agent's config
└── src/my_agent/                        # your code
```

Open your scaffolded agent in **Claude Code**, **Cursor**,
**Aider**, **Codex CLI**, **Windsurf**, or with **GitHub
Copilot** — each tool reads its pointer file (or the canonical
`AGENTS.md` directly), then follows the framework's:

- **File ownership rules** — `AGENTFORGE-MANAGED:` files are
  framework-owned; AI must suggest YAML config changes instead
  of editing them directly. Forked files (`AGENTFORGE-FORKED:`)
  edit freely.
- **Architecture invariants** — don't import vendor SDKs
  directly (use `agent.providers["…"]`), don't write SQL (use
  `agent.memory.put / .get / .query`), don't bypass
  `BudgetPolicy`, don't invent correlation IDs.
- **21 runbooks** — when you ask "add a reranker" / "configure
  multi-provider" / "use streaming guardrails", your AI reads
  the matching runbook and follows it.
- **Anti-patterns** — explicit "do not suggest LangChain idioms
  / `Runnable` / hand-rolled JSON schemas / `try/except` around
  tool code" so AI doesn't hallucinate the wrong framework's
  patterns.

### The developer workflow

1. **Scaffold.** `agentforge new my-support-agent` — instructions
   + 21 runbooks + YAML config land in your repo.
2. **Design.** You focus on **what** your agent does: which
   tools, which reasoning strategy, which memory backend,
   which guardrails. Edit `agentforge.yaml`.
3. **Build.** Your AI coding assistant generates the code,
   reading the relevant runbook and staying inside the
   architecture invariants. You review and iterate.
4. **Upgrade.** `agentforge upgrade --to <new-version>` — new
   runbooks, refreshed instructions, and managed-file diffs
   land via three-way merge. Your custom sections survive
   untouched.

Result: the framework keeps your AI's instructions current as
new capabilities ship. When v0.2.0 added the 5 new runbooks
(reranker, hybrid search, GraphRAG, schema migrations,
streaming guardrails), running `agentforge upgrade` on a v0.1
agent silently teaches your Claude / Cursor / Copilot how to
use them.

---

## What's in the box (v0.2)

| Layer | Modules |
|---|---|
| **LLM providers** | `anthropic`, `openai`, `bedrock`, `ollama` (local), `litellm` (100+ underlying providers) |
| **Embeddings** | `openai` (Matryoshka), `voyage` (multimodal), `bedrock`, `ollama` |
| **Reasoning loops** | ReAct, Plan-Execute, Tree-of-Thoughts, Multi-Agent Supervisor |
| **Persistence** | SQLite, Postgres, Neo4j, SurrealDB — all with `MemoryStore` + `VectorStore` (+ `GraphStore` for graph backends) |
| **Retrieval** | Vector + BM25 hybrid (native: tsvector / FTS5 / Neo4j fulltext / SurrealDB BM25) + RRF fusion + reranker (4 vendor drivers) + GraphRAG expansion |
| **Schema migrations** | `agentforge db migrate` across all 4 vector stores + parameterised vector-dimension migrations |
| **Eval** | Deterministic graders (`Coverage`, `FormatCompliance`, `RegressionVsBaseline`, `Consistency`) + 6 LLM judges (`Correctness`, `Faithfulness`, `Groundedness`, `Hallucination`, `Relevance`, `Helpfulness`) |
| **Production rails** | `BudgetPolicy`, `RunContext` with run_id propagation, `idempotency_key_for`, `FallbackChain` cross-provider failover |
| **Observability** | JSON logs + OTel (with child spans + A2A trace propagation + PII redaction) + Langfuse + Phoenix + Evidently + StatsD |
| **Safety** | Input / Output / Tool-call validators + 4 built-in basics + 4 vendor wrappers (LLM Guard, Presidio, NeMo, Llama Guard) |
| **Protocols** | MCP (stdio + HTTP/SSE) + A2A (HTTP + streaming + discovery + bearer / mTLS auth) |
| **Chat** | `ChatSession` + in-memory / SQLite / Postgres / Redis history + Slack adapter + 4 truncation strategies + sentence-window streaming guardrails |
| **HTTP** | FastAPI chat server (REST + WS + SSE + bearer + rate limit) |
| **CLI** | `agentforge run / eval / debug / db / health / config / list / add / remove / swap / new / upgrade / fork / unfork / status / docs` |

Full per-package list: [`docs/releases/v0.2.0.md`](./docs/releases/v0.2.0.md).

---

## Repository structure

uv workspace — one git repo, **34 installable packages** in
lock-step.

```
agentforge-py/
├── pyproject.toml                       workspace root + shared tool config
├── uv.lock
├── packages/
│   ├── agentforge-core/                 stable contracts (ABCs, value types)
│   ├── agentforge/                      default runtime, CLI, templates
│   ├── agentforge-anthropic/            Anthropic native provider
│   ├── agentforge-openai/               OpenAI provider + embeddings
│   ├── agentforge-bedrock/              AWS Bedrock provider
│   ├── agentforge-litellm/              LiteLLM router wrapper
│   ├── agentforge-ollama/               local Ollama
│   ├── agentforge-voyage/               Voyage embeddings
│   ├── agentforge-memory-{sqlite,postgres,neo4j,surrealdb}/
│   ├── agentforge-chat / chat-http / chat-history-{postgres,redis} / chat-slack/
│   ├── agentforge-reranker-{sentence-transformers,cohere,voyage,mixedbread}/
│   ├── agentforge-guard-{llmguard,presidio,nemo,llamaguard}/
│   ├── agentforge-{mcp,a2a}/            protocols
│   ├── agentforge-{otel,langfuse,phoenix,evidently,statsd}/   observability
│   ├── agentforge-eval-geval/           LLM-judge engine
│   └── agentforge-testing/              golden sets + recordings
├── tests/                               cross-package integration / conformance
├── docs/
│   ├── features/                        canonical feat-NNN specs
│   ├── adr/                             architectural decision records
│   ├── design/                          load-bearing design docs
│   ├── roadmap.md                       shipped + backlog
│   └── releases/                        release notes
└── .github/workflows/                   CI (Linux per-PR; macOS / Windows on demand)
```

Users `pip install` only what they need; each sister package
publishes to PyPI as its own distribution.

---

## Install

```bash
pip install "agentforge-py[anthropic]"
# or
pip install agentforge-py agentforge-openai agentforge-memory-postgres
```

Provider modules (`agentforge-anthropic`, `-openai`,
`-bedrock`, `-ollama`, `-litellm`), embedding modules
(`agentforge-voyage`, etc.), persistence modules
(`agentforge-memory-sqlite` / `-postgres` / `-neo4j`
/ `-surrealdb`), reranker modules, observability backends, and
chat-history adapters all ship as separate packages.

---

## Development

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:Scaffoldic/agentforge-py.git
cd agentforge-py
uv sync --all-extras --dev        # venv + members + dev deps
uv run pre-commit install         # git hooks (mirror CI)
uv run pre-commit run --all-files # full gate (ruff + mypy + bandit + pytest + ≥90% cov)
```

CI is split per-OS:

- **`ci-linux.yml`** runs on every PR + push to `main` — lint,
  types, tests, live integration (Postgres + Redis services),
  coverage ratchet.
- **`ci-windows.yml`** + **`ci-mac.yml`** run on
  `workflow_dispatch` only — invoke before cutting a release
  or when touching path / subprocess / filesystem code.

---

## Roadmap

[`docs/roadmap.md`](./docs/roadmap.md) tracks shipped + backlog.
v0.3 candidates: `down` migrations, native single-Cypher
GraphRAG, multi-cluster Redlock, true streaming-aware redact,
Evidently Cloud, optional eval adapters (Ragas / DeepEval /
Toxicity / CodeExec), TypeScript port.

---

## Contributing

Before you start: read [`AGENTS.md`](./AGENTS.md) for repo
conventions (workspace layout, locked contract layer,
anti-patterns reviewers will reject, pre-commit gate, how to
add a new module package).

- Branch from `main`: `feat/<NNN>-<slug>`, `fix/<slug>`,
  `docs/<slug>`, `chore/<slug>`.
- Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`,
  `refactor:`, `chore:`, `perf:`, `revert:`.
- One feature = one PR. Squash-merge to `main`.
- 90% coverage gate; pre-commit + CI block below.
- Every feature PR updates its canonical spec's
  `Implementation status` section before merge.

---

## License

Apache 2.0. See [`LICENSE`](./LICENSE) and [`NOTICE`](./NOTICE).
