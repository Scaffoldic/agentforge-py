# Feature catalogue

> The full list of features that make up AgentForge. Each row is an entry point
> for a future `feat-NNN-{slug}.md` doc (template:
> [`/.claude/templates/feature.md`](../../.claude/templates/feature.md)).
>
> This catalogue is the **first pass** — call out missing features, merge or split
> rows, before we commit to writing the individual feature docs.

---

## Status legend

- `proposed` — listed here, no individual doc yet
- `accepted` — individual feature doc exists and is approved
- `in-progress` — implementation underway
- `shipped` — released in a tagged version
- `deferred` — agreed, not in current milestone
- `dropped` — decided against; row kept for history

## Versioning targets

- **0.1** — minimum viable framework: hello-world in 3 lines, **all four reasoning loops (ReAct + Plan-Execute + ToT + Multi-Agent) shipped stable**, in-memory state, one provider, basic tools, scaffolding `new`, basic safety defaults (prompt-injection regex + PII redaction + tool capability gate), runbooks + `AGENTS.md` shipped in every scaffold.
- **0.2** — modules: `add module`, persistence drivers (SQLite + Postgres), MCP, evaluators (deterministic + LLM-judge), full safety guardrail module ecosystem (LLM Guard, Presidio, NeMo, Llama Guard), chat agents (`ChatSession` + memory/sqlite history + HTTP/WebSocket/SSE server).
- **0.3** — upgrade: `agentforge upgrade` with three-way merge; remaining persistence drivers (SurrealDB + Neo4j); remaining chat history drivers (Postgres + Redis); reference channel adapter (Slack).
- **0.4** — TypeScript reaches parity with Python 0.2 surface.
- **1.0** — stability bar: contracts frozen, semver enforced, full evaluator + observability + safety stack.

## The features

### Core framework

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-001** | Core contracts & `Agent` orchestrator | shipped (Python; TS pending) | 0.1 | both | `agentforge-core`, `agentforge` |
| **feat-002** | Reasoning strategies (ReAct stable; Plan-Execute / ToT / Multi-Agent experimental) | proposed | 0.1 (ReAct), 0.3 (rest) | both | `agentforge`, `agentforge-strategies-experimental` |
| **feat-003** | LLM & embedding providers — `LLMClient` + `EmbeddingClient`, named-provider registry (multi-LLM agents: reasoning + judge + embedding), capability negotiation | proposed | 0.1 | both | `agentforge-core` + provider modules (`agentforge-anthropic`, `-bedrock`, `-openai`, `-voyage`, ...) |
| **feat-004** | Tools system (`@tool` decorator, `Tool` ABC, default tool set) | proposed | 0.1 | both | `agentforge` |
| **feat-005** | Persistence — `MemoryStore` ABC + drivers (sqlite, postgres, surrealdb, neo4j) | proposed | 0.2 (sqlite, postgres), 0.3 (surrealdb, neo4j) | both | `agentforge-memory-*` |
| **feat-006** | Evaluators (deterministic + LLM-judge: correctness, faithfulness, groundedness, hallucination, relevance, helpfulness, coverage, format compliance, regression, consistency) | shipped (Python) | 0.2 | both | `agentforge`, `agentforge-eval-geval`, optional `-ragas`, `-deepeval`, `-toxicity`, `-codeexec` |
| **feat-007** | Production rails — cost & resilience (budget, fallback chain, run_id propagation, idempotency) | proposed | 0.1 | both | `agentforge-core`, `agentforge` |
| **feat-008** | Findings & output shapes (Simple/Patch/Narrative/MultiSpan + renderers) | shipped (Python) | 0.1 | both | `agentforge`, `agentforge-core` |
| **feat-009** | Observability — structured logging (JSON) + distributed tracing (OTel) + hook fan-out; vendor backends (Langfuse / Phoenix / Evidently / StatsD) deferred to follow-up sub-feats | shipped (Python, OTel only) | 0.2 | both | `agentforge`, `agentforge-otel`, future `agentforge-langfuse`, `agentforge-phoenix`, `agentforge-evidently`, `agentforge-statsd` |

### Safety & security

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-018** | Safety guardrails — `InputValidator` / `OutputValidator` / `ToolCallGate` ABCs; built-in prompt-injection + PII + capability gates; modules for LLM Guard, Presidio, NeMo Guardrails, Llama Guard | proposed | 0.1 (basics), 0.2 (full ecosystem) | both | `agentforge` (built-ins), `agentforge-guard-llmguard`, `agentforge-guard-presidio`, `agentforge-guard-nemo`, `agentforge-guard-llamaguard` |

### Module system

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-010** | Module discovery & resolution — entry-point auto-load + `Resolver.list_installed` + `agentforge list modules` CLI; destructive `add/swap/remove` deferred alongside feat-012 | shipped (Python, read-only) | 0.2 | both | `agentforge` (CLI), `agentforge-core` (resolver) |
| **feat-011** | Scaffolding & upgrade (`agentforge new`, `agentforge upgrade`, `agentforge fork`, six starter templates, marker-header file ownership) | proposed | 0.1 (new), 0.3 (upgrade) | both | `agentforge` (CLI), `agentforge-templates` (template repo) |
| **feat-012** | Configuration system (`agentforge.yaml` schema, env var interpolation, validation, dotted-path overrides, layered env files, module-side schema integration, `agentforge config` CLI) | shipped (Python) | 0.1 | both | `agentforge-core`, `agentforge` |

### Protocols & interop

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-013** | MCP integration (consume MCP tool servers; expose agent tools as MCP server) | proposed | 0.2 | both | `agentforge-mcp` |
| **feat-014** | A2A (agent-to-agent) protocol support — for cross-framework agent calls | proposed | 0.4 (after stability) | both | `agentforge-a2a` |

### Deployment shapes

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-020** | Chat agents — `ChatSession` wrapper, `ChatHistoryStore` (memory/sqlite/postgres/redis drivers), streaming, HTTP/WebSocket/SSE server, multi-tenant isolation, per-turn cost/guardrails, idempotency, cancellation | proposed | 0.2 (contracts + memory + sqlite + chat-http), 0.3 (postgres + redis + reference channel adapter) | both | `agentforge-chat`, `agentforge-chat-history-postgres`, `agentforge-chat-history-redis`, `agentforge-chat-http`, optional `agentforge-chat-slack` |

### Pipeline

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-015** | Pipeline & deterministic tasks (`Pipeline`, `Task` ABC, parallel/sequential execution) | proposed | 0.2 | both | `agentforge` |

### Developer experience

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-016** | Testing framework (MockLLMClient / fake tools / pytest fixtures / vitest helpers) | proposed | 0.1 | both | `agentforge`, `agentforge-testing` |
| **feat-017** | CLI runtime — `agentforge run`, `agentforge eval`, `agentforge debug`, `agentforge db migrate`, `agentforge list`, `agentforge docs` | proposed | 0.1 (run), 0.2 (rest) | both | `agentforge` |
| **feat-019** | Developer experience — 16 runbooks + `AGENTS.md` / `CLAUDE.md` / `.cursorrules` rules shipped with every scaffolded agent; `agentforge docs` CLI; managed via Copier so they upgrade with the framework | proposed | 0.1 (initial set) | both | `agentforge-templates`, `agentforge` |

---

## Cross-cutting concerns (not features, but tracked here)

- **Cross-language parity policy.** Documented in `architecture.md` §10. Each
  feature doc declares its `Languages` field; Python ships first during 0.x, TS
  catches up by 0.4.
- **Conformance test suites.** Every ABC ships a conformance suite that all drivers
  pass. Tracked inside the relevant feature doc, not as a separate feature.
- **Documentation.** Runbooks, quickstart guides, and per-module READMEs are
  shipped with the relevant feature, not separately tracked.
- **Release engineering.** Coordinated release train across `agentforge-core`,
  `agentforge`, and the module packages. Defined in `architecture.md` §10 and
  governed by versioning rules in `design-principles.md` (P1, P12).

## What's deliberately not here

- **No "framework agnostic" abstraction layer.** We don't try to wrap LangChain,
  LlamaIndex, etc. Importing them as tools is fine; framework-of-frameworks is not
  on the roadmap.
- **No vector store abstraction in core.** Embeddings + retrieval is a tool-level
  concern, not a primitive. (Discussed in `persistence-and-orm.md` §3.)
- **No prompt-template engine.** Strings + f-strings (Python) / template literals
  (TS) are sufficient. We don't ship Jinja-for-prompts.
- **No no-code UI.** The audience is engineers; UIs come from the community if
  they come at all.
- **No "research mode" / experimental sandbox.** New ideas land as features behind
  experimental flags inside the relevant module, not in a separate playground.

## How to use this catalogue

- A new feature is added by inserting a row above and creating
  `feat-NNN-{slug}.md` from the template.
- A row never gets a number-shuffled neighbour; numbers are immutable once
  assigned.
- A row's `Status` is updated as the feature progresses; this catalogue is the
  source of truth for "what's the state of AgentForge?".
- A row that is `dropped` stays in the catalogue (history matters); a row that is
  `deferred` is moved to the bottom of its category.

## Next steps

1. Review the full feature set (18 features as of 2026-05-09). Each feature
   doc is filled in under `docs/features/feat-NNN-{slug}.md`.
2. Resolve the open questions flagged in §8 of each feature doc. Highest-
   priority unresolved decisions: TS scoping (`agentforge` flat vs
   `@agentforge/core`), Copier vs native-TS upgrade tool, A2A auth backends,
   guardrail latency budgeting.
3. Scaffold `python/agentforge-py/` package skeleton matching feat-001's
   contracts; begin v0.1 critical-path implementation.
4. In parallel, lock the lockfile/release-train policy described in
   `architecture.md` §10 to avoid LlamaIndex-style version-matrix drift.
