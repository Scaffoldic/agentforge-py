<!--
  This is the PyPI landing page for the `agentforge-py` distribution.
  It mirrors the repository root README.md, but every link is ABSOLUTE
  (https://github.com/Scaffoldic/agentforge-py/...) because PyPI does
  not resolve repo-relative links or images. When you update the root
  README, update this file too and keep the links absolute.
-->

# AgentForge

**An AI-agent framework that behaves like infrastructure, not a demo you
ship once.**
Production plumbing — cost, tracing, memory, guardrails, failover — comes as
swap-by-config packages behind version-locked contracts. You write your use
case; the framework is already production-grade.

[![PyPI](https://img.shields.io/pypi/v/agentforge-py.svg)](https://pypi.org/project/agentforge-py/)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://github.com/Scaffoldic/agentforge-py)
[![License](https://img.shields.io/badge/license-Apache_2.0-blue.svg)](https://github.com/Scaffoldic/agentforge-py/blob/main/LICENSE)

![Scaffold a complete agent project, run the full loop offline with budget and tracing wired in, then swap the vendor or the reasoning loop by editing one line of YAML — the agent code never changes](https://raw.githubusercontent.com/Scaffoldic/agentforge-py/main/examples/swap-by-config/demo.gif)

*From zero: `agentforge new` scaffolds a runnable project → the full loop runs
**offline, no API key** (a recorded run) with budget + tracing already wired →
swap the vendor *or* the reasoning loop by editing **one line of YAML**,
`agent.py` never changes.*
[Runnable example →](https://github.com/Scaffoldic/agentforge-py/tree/main/examples/swap-by-config)

> **AgentForge treats an agent like a system you operate, not a demo
> you ship once.** Four things at its core:
>
> 1. **Version-locked contracts.** ~30 ABCs in a small
>    `agentforge-core` describe the agent surface, and breaking one
>    is a *major* version bump (ADR-0007) — so you can build on them
>    like a stable API.
> 2. **Every backend is its own package, swapped by config.** LLM
>    provider, memory store, observability stack, reranker, guardrail
>    — each ships as a separate PyPI distribution you plug in and swap
>    by editing one line of YAML, never your agent code.
> 3. **The reasoning loop is swap-by-config too.** ReAct,
>    Plan-and-Execute, Tree-of-Thoughts, and a Multi-Agent Supervisor
>    ship behind one `Strategy` contract — pick the loop in YAML, or
>    compose your own from the ABC. The same agent code runs under any
>    of them; the strategy is a configuration choice, not a rewrite.
> 4. **Scaffolds keep your AI coding assistant on-idiom.** Every
>    generated project ships framework-aware instructions for **Claude
>    Code, Cursor, GitHub Copilot, Aider, Codex, and Windsurf** plus
>    task runbooks — so the AI helping you build stays inside the
>    framework's conventions automatically.
>
> Cost guardrails, OpenTelemetry tracing, vendor failover, PII
> redaction, and reproducible evals are wired in too — behind those
> same locked contracts, so you can depend on them in production.

```python
from agentforge import Agent

async with Agent(model="anthropic:claude-sonnet-4-7") as agent:
    result = await agent.run("Summarise this PR in three bullets.")
    print(result.output)
```

Swap `anthropic:` for `openai:`, `bedrock:`, `ollama:`, or
`litellm:` — same code, different vendor. Swap the reasoning loop the
same way: `strategy: react` → `plan-execute` → `tree-of-thoughts` →
`supervisor`, no code change. Every swap happens *behind a locked
contract*, so it can't quietly change the shape of what your agent gets
back.

---

## Why AgentForge

### For developers
The plumbing every production agent needs — cost limits, run-id
propagation, distributed tracing, vendor failover, durable state,
prompt-injection defenses, PII redaction, hybrid retrieval — is
**configured, not coded**. You focus on what your agent *does*,
not on the harness around it.

### For organisations
Audit-ready by default. Every call traces through OpenTelemetry
with run_id propagation. Cost guardrails reject runs that exceed
their budget *before* the LLM bill lands. PII redaction happens
inside the framework, not in app code. Built-in evaluators turn
"did this prompt change regress?" into a reproducible CI gate.
SOC 2 / GDPR / ISO 27001 conversations get shorter.

### For your AI coding assistant
Every scaffolded agent ships with framework-aware instructions
for **Claude Code, Cursor, GitHub Copilot, Aider, Codex CLI, and
Windsurf** — plus 21 task-oriented runbooks. Your AI builds
inside the framework's idioms automatically. `agentforge upgrade`
keeps the instructions current as new capabilities ship, so the AI
learns the new APIs without you teaching it.

---

## Quick start

**Day 1 — install, scaffold, run:**

```bash
pip install "agentforge-py[anthropic]"   # or [openai], [bedrock], [ollama], [litellm]
agentforge new my-agent --template minimal
cd my-agent

export ANTHROPIC_API_KEY=sk-ant-…
agentforge run "Hi"
```

Six starter templates ship in the wheel: `minimal`, `code-reviewer`,
`patch-bot`, `docs-qa`, `triage`, `research`.

> **Want proof before you install a provider?**
> [`examples/swap-by-config/`](https://github.com/Scaffoldic/agentforge-py/tree/main/examples/swap-by-config)
> runs the full agent loop **offline with no API key** (`python smoke.py`), and
> shows the same `agent.py` driving Anthropic or OpenAI with a one-line config
> change.

**Day N — add modules, swap backends, upgrade the framework:**

```bash
# add a sister module (memory backend, reranker, observability, guard, protocol…)
pip install agentforge-memory-postgres
agentforge add memory-postgres
agentforge config validate

# swap providers / strategies / backends without touching code
agentforge swap llm openai

# upgrade the framework — managed files + runbooks refresh,
# your custom code + `<!-- agentforge:custom -->` blocks survive
agentforge upgrade --to 0.4.0
```

Every command has a matching `docs/runbooks/NN-*.md` step-by-step
guide that ships in the scaffold — your AI coding assistant
follows the relevant runbook automatically when you ask it for
"add a reranker" / "configure multi-provider" / "use streaming
guardrails".

---

## What's in the box

AgentForge is a **contracts-first** framework: ~30 locked ABCs in
`agentforge-core` describe the agent surface; everything else is a
plug-in module shipped as its own PyPI package. Pick the modules
you need, swap them via config when requirements change.

### Pluggable providers
LLMs: Anthropic · OpenAI · AWS Bedrock · Ollama (local) · LiteLLM
(100+ underlying providers). Embeddings: OpenAI Matryoshka · Voyage
multimodal · Bedrock · Ollama. One string ID
(`anthropic:claude-sonnet-4-7`) selects the model; no
provider-specific code paths in your agent.

### Reasoning strategies
ReAct · Plan-and-Execute · Tree-of-Thoughts · Multi-Agent
Supervisor. Pick the loop in YAML, compose your own from the
strategy ABC when you need to.

### Persistence + retrieval
One `MemoryStore` + `VectorStore` (+ `GraphStore`) contract, five
backends: SQLite · Postgres · Neo4j · SurrealDB · Kùzu (embedded,
zero-ops graph). Hybrid retrieval (vector + BM25 over native
indexes, RRF fusion), four reranker vendors, directional GraphRAG
expansion for graph backends, schema migrations across all stores
via `agentforge db migrate`.

### Guardrails — cost, safety, reliability
**Cost.** `BudgetPolicy` checks every LLM, tool, and retriever
call against the run's budget — over-budget runs fail fast,
before the bill lands.
**Safety.** Input / output / tool-call validator pipelines with
four built-in basics + four vendor wrappers — **LLM Guard,
Microsoft Presidio, NVIDIA NeMo Guardrails, Meta Llama Guard** —
for PII, prompt injection, toxicity, and off-topic detection.
**Reliability.** Run-id propagation, `idempotency_key_for()` for
side-effecting tools, `FallbackChain` cross-provider failover.

### Governance
A governance spine behind locked contracts: typed `Principal`
identities (`kind` / `owner`) and an `IdentityProvider` contract,
with an offline `local` driver (HMAC, URN ids) in the
`agentforge-governance` package — the foundation for registry,
policy-as-code, and audit (ADR-0023).

### Observability
JSON-structured logs + OpenTelemetry (with child spans, A2A
trace propagation, PII redaction) + Langfuse + Arize Phoenix +
Evidently + StatsD. Everything wires in via config; nothing to
instrument in your agent code.

### Evaluation
Deterministic graders — Coverage, FormatCompliance,
RegressionVsBaseline, Consistency — plus six LLM judges
(Correctness, Faithfulness, Groundedness, Hallucination,
Relevance, Helpfulness). Turn prompt and model upgrades into a
CI gate.

### Chat + protocols
`ChatSession` with in-memory / SQLite / Postgres / Redis history,
four truncation strategies, sentence-window streaming guardrails
(PII redaction over a streamed response), and a Slack adapter.
**MCP** stdio + HTTP/SSE servers. **A2A** HTTP + streaming +
discovery + bearer / mTLS auth.

### CLI
`agentforge run` · `eval` · `debug` · `db migrate` · `health` ·
`config validate` · `list` / `add` / `remove` / `swap` (module
management) · `new` · `upgrade` · `fork` / `unfork` · `status` ·
`docs`.

---

## Build your own agent

> **You don't need to clone the repository.** AgentForge ships as
> PyPI packages — your agent lives in *your own project*, with the
> framework as a dependency. Cloning the repo is only for
> [contributing to the framework itself](https://github.com/Scaffoldic/agentforge-py/blob/main/CONTRIBUTING.md).

### 1. Install from PyPI

```bash
pip install "agentforge-py[anthropic]"   # or [openai], [bedrock], [ollama], [litellm]
# combine extras
pip install "agentforge-py[anthropic,openai,memory-postgres,otel]"
# or install sister packages directly
pip install agentforge-py agentforge-memory-postgres agentforge-langfuse
```

Every module is its own PyPI distribution. Install only what you
use; the framework lazy-imports vendor SDKs so unused providers
don't add startup cost.

### 2. Scaffold your agent project

```bash
agentforge new my-agent --template minimal
cd my-agent
```

Pick from six templates: `minimal`, `code-reviewer`, `patch-bot`,
`docs-qa`, `triage`, `research`. You get a complete, runnable
project:

```
my-agent/
├── agentforge.yaml     # model, strategy, budget — the swap-by-config surface
├── pyproject.toml
├── .env.example        # copy to .env, add your API key
├── src/my_agent/
│   └── main.py         # your agent code — start editing here
├── docs/runbooks/      # step-by-step guides your AI assistant follows
├── AGENTS.md           # framework-aware instructions for AI coding
└── CLAUDE.md           # assistants (Claude Code, Cursor, Copilot, …)
```

### 3. Add your API key

```bash
cp .env.example .env    # then set ANTHROPIC_API_KEY=sk-ant-…
```

### 4. Write what your agent does

Edit `src/my_agent/main.py`. Give the agent your own tools — a
typed function plus the `@tool` decorator is all it takes (the
input schema is inferred from the signature and docstring):

```python
from agentforge import Agent, tool

@tool
def lookup_order(order_id: str) -> dict:
    """Fetch an order record from your backend."""
    return orders_db.get(order_id)

async with Agent(tools=[lookup_order]) as agent:
    result = await agent.run("What's the status of order 1042?")
    print(result.output)
```

Stateful tools subclass the `Tool` ABC instead. Four defaults ship
in `agentforge.tools`: `web_search`, `calculator`, `file_read`,
`shell`.

### 5. Configure behaviour in YAML, not code

`agentforge.yaml` is where the model, reasoning strategy, and
guardrails live — your Python never names a vendor:

```yaml
agent:
  model: "anthropic:claude-sonnet-4-5"
  strategy: "react"        # swap-by-config: plan-execute · tree-of-thoughts · supervisor
  budget:
    usd: 2.0               # over-budget runs fail before the bill lands
```

Switching providers is `agentforge swap llm openai` — one config
line changes, your agent code doesn't.

### 6. Run and validate

```bash
agentforge run "What's the status of order 1042?"
agentforge config validate
```

### 7. Grow it as your needs grow

```bash
# durable state, tracing, safety, retrieval — one pip install + one `add` each
pip install agentforge-memory-postgres && agentforge add memory-postgres
pip install agentforge-otel            && agentforge add otel

# framework upgrades refresh managed files; your custom code survives
agentforge upgrade --to 0.4.0
```

Memory backends, rerankers, guardrail vendors, observability
stacks, MCP/A2A protocols, evaluators — every capability in
[What's in the box](#whats-in-the-box) plugs in the same way, and
each has a matching `docs/runbooks/NN-*.md` guide in your scaffold
that your AI coding assistant follows automatically.

---

## Repository structure

uv workspace — one git repo, 36 installable packages in lock-step.

```
agentforge-py/
├── packages/
│   ├── agentforge-core/                                          locked contracts (~30 ABCs)
│   ├── agentforge/                                               default runtime + CLI + templates
│   ├── agentforge-{anthropic,openai,bedrock,ollama,litellm}/     LLM providers
│   ├── agentforge-voyage/                                        embeddings
│   ├── agentforge-memory-{sqlite,postgres,neo4j,surrealdb,kuzu}/ persistence
│   ├── agentforge-reranker-{cohere,voyage,mixedbread,sentence-transformers}/
│   ├── agentforge-guard-{llmguard,presidio,nemo,llamaguard}/     safety
│   ├── agentforge-governance/                                    identity + governance spine
│   ├── agentforge-{otel,langfuse,phoenix,evidently,statsd}/      observability
│   ├── agentforge-{mcp,a2a}/                                     protocols
│   ├── agentforge-chat / chat-http / chat-history-{postgres,redis} / chat-slack/
│   ├── agentforge-eval-geval/                                    LLM judges
│   └── agentforge-testing/                                       golden sets + recordings
├── docs/features/                                                canonical feat-NNN specs
├── docs/design/                                                  architecture + module system
├── docs/adr/                                                     immutable decision records
└── docs/roadmap.md                                               shipped + backlog
```

---

## Development (contributing to the framework)

You only need this section to work on AgentForge itself. To
**build an agent**, you never clone the repo — see
[Build your own agent](#build-your-own-agent).

Prereqs: Python 3.13 + [uv](https://docs.astral.sh/uv/).

```bash
git clone git@github.com:Scaffoldic/agentforge-py.git
cd agentforge-py
uv sync --all-extras --dev
uv run pre-commit install
uv run pre-commit run --all-files   # ruff + mypy + bandit + pytest + ≥90 % cov
```

Linux CI runs on every PR. Windows and macOS CI run on
`workflow_dispatch` — invoke before cutting a release or when
touching path / subprocess / filesystem code.

---

## Status

**Early but production-minded.** AgentForge is `v0.4.x` and
solo-maintained — the API surface is stabilising, the contracts are
locked (ADR-0007), and it's tested like infrastructure
(`mypy --strict`, ≥90 % coverage, a conformance harness every backend
must pass, live integration tests in CI). Issues, feedback, and
contributors are very welcome.

---

## Contributing

Start with [`CONTRIBUTING.md`](https://github.com/Scaffoldic/agentforge-py/blob/main/CONTRIBUTING.md)
— setup, the hard rules, branch/PR conventions, and the pre-commit gate. The
deeper conventions live in
[`AGENTS.md`](https://github.com/Scaffoldic/agentforge-py/blob/main/AGENTS.md).
Be excellent to each other:
[`CODE_OF_CONDUCT.md`](https://github.com/Scaffoldic/agentforge-py/blob/main/CODE_OF_CONDUCT.md).
Found a security issue? See
[`SECURITY.md`](https://github.com/Scaffoldic/agentforge-py/blob/main/SECURITY.md)
(please report privately).

- Branch from `main`: `feat/<NNN>-<slug>`, `fix/<slug>`,
  `docs/<slug>`, `chore/<slug>`
- Conventional Commits
- One feature = one PR, squash-merged
- 90 % coverage floor
- Every feature PR updates its spec's `Implementation status`

Looking for somewhere to start? Issues labelled `good first issue`
and `help wanted`, plus the
[`docs/roadmap.md`](https://github.com/Scaffoldic/agentforge-py/blob/main/docs/roadmap.md)
backlog.

---

## Roadmap

[`docs/roadmap.md`](https://github.com/Scaffoldic/agentforge-py/blob/main/docs/roadmap.md)
tracks shipped + backlog.

---

## License

Apache 2.0. See
[`LICENSE`](https://github.com/Scaffoldic/agentforge-py/blob/main/LICENSE) and
[`NOTICE`](https://github.com/Scaffoldic/agentforge-py/blob/main/NOTICE).
