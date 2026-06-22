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
- **0.2** — modules + ecosystem: `add module`, persistence drivers (SQLite + Postgres + SurrealDB + Neo4j), MCP (incl. production runner), A2A (incl. production runner + discovery + bi-directional streaming), evaluators (deterministic + LLM-judge), full safety guardrail module ecosystem (LLM Guard, Presidio, NeMo, Llama Guard), chat agents full stack (memory + sqlite + postgres + redis history drivers + chat-http + slack reference adapter + real per-token streaming + cross-process locking), vendor observability backends (Langfuse, Phoenix, Evidently, StatsD), advanced retrieval (GraphRAG hybrid, BM25 + vector fusion, `Reranker` ABC, schema migrations).
- **0.3** — reserved for the next round of community / ecosystem feedback; intentionally empty at v0.1.0 cut. Use this slot when 0.2 starts to overflow.
- **0.4** — TypeScript reaches parity with Python 0.2 surface.
- **1.0** — stability bar: contracts frozen, semver enforced, full evaluator + observability + safety stack.

## The features

### Core framework

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-001** | Core contracts & `Agent` orchestrator | shipped (Python; TS pending) | 0.1 | both | `agentforge-core`, `agentforge` |
| **feat-002** | Reasoning strategies (ReAct + Plan-Execute + ToT + Multi-Agent — all stable from v0.1) | shipped (Python) | 0.1 | both | `agentforge` (all four loops in-runtime) |
| **feat-003** | LLM & embedding providers — `LLMClient` + `EmbeddingClient`, named-provider registry (multi-LLM agents: reasoning + judge + embedding), capability negotiation | shipped (Python — ABCs + registry + `agentforge-bedrock` in 0.1; first-party sister packages `agentforge-anthropic` / `-openai` / `-voyage` / `-litellm` / `-ollama` ship in 0.2) | 0.1 (ABCs + registry + Bedrock), 0.2 (first-party sister packages) | both | `agentforge-core` + `agentforge-bedrock` (0.1), `agentforge-anthropic`, `agentforge-openai`, `agentforge-voyage`, `agentforge-litellm`, `agentforge-ollama` (0.2) |
| **feat-004** | Tools system (`@tool` decorator, `Tool` ABC, default tool set, `FakeTool`) | shipped (Python) | 0.1 | both | `agentforge` |
| **feat-005** | Persistence — `MemoryStore` ABC + drivers (sqlite, postgres, surrealdb, neo4j) + `VectorStore` + `GraphStore` + RAG | shipped (Python — full surface; PRs #5/#7/#8 mis-labelled per spec §10) | 0.1 | both | `agentforge-memory-sqlite`, `-postgres`, `-neo4j`, `-surrealdb` |
| **feat-006** | Evaluators (deterministic + LLM-judge: correctness, faithfulness, groundedness, hallucination, relevance, helpfulness, coverage, format compliance, regression, consistency) | shipped (Python) | 0.1 | both | `agentforge`, `agentforge-eval-geval`, optional `-ragas`, `-deepeval`, `-toxicity`, `-codeexec` |
| **feat-007** | Production rails — cost & resilience (budget, fallback chain, run_id propagation, idempotency) | shipped (Python) | 0.1 | both | `agentforge-core`, `agentforge` |
| **feat-008** | Findings & output shapes (Simple/Patch/Narrative/MultiSpan + renderers) | shipped (Python) | 0.1 | both | `agentforge`, `agentforge-core` |
| **feat-009** | Observability — structured logging (JSON) + distributed tracing (OTel) + hook fan-out; vendor backends (Langfuse / Phoenix / Evidently / StatsD) slated for v0.2 | shipped (Python, OTel only) | 0.1 (framework + OTel — shipped), 0.2 (vendor backends) | both | `agentforge`, `agentforge-otel`, future `agentforge-langfuse`, `agentforge-phoenix`, `agentforge-evidently`, `agentforge-statsd` |
| **feat-026** | Application config extension — reserved `app:` namespace + typed `app_as()` accessor (Phase 1), registered typed sections validated via the module-schema engine + entry points (Phase 2), pluggable config sources / separate files via `imports:` (Phase 3). Lets agents built on AgentForge reuse the config machinery (interpolation, layering, `--resolved`, uniform validation). Reported via #86 | shipped (all 3 phases → 0.3.0) | 0.3.0 | both | `agentforge-core`, `agentforge` |
| **feat-027** | Embedded `GraphStore` — `KuzuGraphStore`, a zero-ops, file-backed, in-process graph driver (the graph analogue of the SQLite `MemoryStore`). Implements the locked `GraphStore` ABC and passes `run_graph_conformance`, so it is swap-compatible with Neo4j/SurrealDB; `path: .ckg` and the store exists — no server. Makes the whole graph + GraphRAG path testable offline. Drives the `agentforge-graph` code-graph dogfood | implemented (0.4) | 0.4 | python (TS deferred) | new `agentforge-memory-kuzu` |
| **feat-028** | Durable execution + human-in-the-loop — checkpoint-and-resume so a run survives process death (resumes at the failed step, no double-spend / double-fire), plus approval gates that suspend before irreversible tool calls and resume on human approve/deny/edit. Promotes the feat-017 record/replay seam into a checkpoint seam (`__checkpoint` claims on a `MemoryStore`); budget snapshot + idempotency-seed restore for correctness; `execution:` / `human_in_the_loop:` config blocks; additive `Agent` kwargs. Foundational execution infrastructure every production agent eventually needs | proposed | 0.5 | python (TS deferred) | `agentforge-core`, `agentforge`, checkpoint driver pkg(s) |

### Safety & security

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-018** | Safety guardrails — `InputValidator` / `OutputValidator` / `ToolCallGate` ABCs; built-in prompt-injection + PII + capability gates; modules for LLM Guard, Presidio, NeMo Guardrails, Llama Guard | shipped (Python — ABCs + built-ins + 4 vendor packages) | 0.1 | both | `agentforge-core` (ABCs + values + conformance), `agentforge` (built-ins + engine), `agentforge-guard-llmguard`, `agentforge-guard-presidio`, `agentforge-guard-nemo`, `agentforge-guard-llamaguard` |

### Module system

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-010** | Module discovery & resolution — entry-point auto-load + `Resolver.list_installed` + full `agentforge list/add/remove/swap module` CLI + manifest-driven module wiring | shipped (Python) | 0.1 | both | `agentforge` (CLI), `agentforge-core` (resolver + manifest) |
| **feat-011** | Scaffolding & upgrade (`agentforge new`, `agentforge upgrade`, `agentforge fork`, six starter templates, marker-header file ownership) | shipped (Python) | 0.1 | both | `agentforge` (CLI; templates ship in-wheel) |
| **feat-012** | Configuration system (`agentforge.yaml` schema, env var interpolation, validation, dotted-path overrides, layered env files, module-side schema integration, `agentforge config` CLI) | shipped (Python) | 0.1 | both | `agentforge-core`, `agentforge` |

### Protocols & interop

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-013** | MCP integration — `MCPServerClient` (stdio + HTTP/SSE) consumes upstream tool servers via `MCPToolAdapter`; `MCPServer` exposes local tools; `MCPBridge.from_config` orchestrates from `modules.protocols.mcp` | shipped (Python — contracts + adapter + client + server + bridge; production runner slated for v0.2) | 0.1 (shipped scope), 0.2 (production runner) | both | `agentforge-mcp` |
| **feat-014** | A2A (agent-to-agent) protocol support — for cross-framework agent calls | shipped (Python — contracts + client + server + bridge; production runner + discovery + bi-directional streaming slated for v0.2) | 0.1 (shipped scope), 0.2 (production runner + discovery + streaming) | both | `agentforge-a2a` |

### Deployment shapes

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-020** | Chat agents — `ChatSession` wrapper, `ChatHistoryStore` (memory/sqlite/postgres/redis drivers), streaming, HTTP/WebSocket/SSE server, multi-tenant isolation, per-turn cost/guardrails, idempotency, cancellation | shipped (Python v0.1 scope: contracts + memory + sqlite + chat-http); v0.2 follow-up scope tracked in spec §10 | 0.2 (full stack: postgres + redis history + slack adapter + real streaming + cross-process lock + tokeniser) | both | `agentforge-chat`, `agentforge-chat-history-postgres`, `agentforge-chat-history-redis`, `agentforge-chat-http`, optional `agentforge-chat-slack` |

### Pipeline

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-015** | Pipeline & deterministic tasks (`Pipeline`, `Task` ABC, parallel/sequential execution) | shipped (Python) | 0.1 | both | `agentforge` |

### Developer experience

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-016** | Testing framework — `agentforge.testing` namespace (MockLLMClient + FakeTool + agent_factory + pytest fixtures + record_llm/replay + conformance re-exports) + `agentforge-testing` package (GoldenSetRunner + assert_snapshot + analyze_recording) | shipped (Python) | 0.1 | both | `agentforge`, `agentforge-testing` |
| **feat-017** | CLI runtime — `agentforge run` (+ `--replay`), `agentforge eval`, `agentforge debug`, `agentforge db {migrate,backup,restore,purge,query}`, `agentforge health` (preflight) | shipped (Python) | 0.1 | both | `agentforge` (CLI), `agentforge-core` (`MemoryStore.delete` ABC addition) |
| **feat-019** | Developer experience — 16 runbooks + `AGENTS.md` / `CLAUDE.md` / `.cursorrules` rules shipped with every scaffolded agent; `agentforge docs` CLI (list / open / drift-check / serve); three-section managed/custom file format with upgrade-safe custom preservation | shipped (Python) | 0.1 (initial set) | both | `agentforge` (CLI + templates._shared) |

### Retrieval

| ID | Title | Status | Target | Languages | Module(s) |
|---|---|---|---|---|---|
| **feat-021** | Reranker — cross-encoder reranking on top of vector retrieval; `Reranker` ABC + `Retriever(reranker=...)` integration with configurable over-fetch + SentenceTransformers default concrete impl | shipped (Python) | 0.2 | both | `agentforge-core` (ABC), `agentforge` (Retriever integration), `agentforge-reranker-sentence-transformers` |
| **feat-022** | Hybrid search — `VectorStore.lexical_search` ABC extension + pure-Python BM25 (`_BM25Index`) + `Retriever(mode="hybrid")` with RRF fusion + `InMemoryVectorStore` / `PostgresVectorStore` (tsvector + ts_rank_cd) / `SqliteVectorStore` (FTS5 + bm25) native impls + opt-in `run_hybrid_search_conformance` suite | shipped (Python) | 0.2 | both | `agentforge-core` (ABC + BM25 + conformance), `agentforge` (Retriever hybrid mode + InMemoryVectorStore impl), `agentforge-memory-postgres` (native tsvector), `agentforge-memory-sqlite` (native FTS5) |
| **feat-023** | GraphRAG hybrid retrieval — `GraphExpansion` value type + `Retriever(graph_expansion=...)` for post-retrieve N-hop graph traversal expansion + score-decay merge + dedup. Composes orthogonally with `mode="vector"` / `mode="hybrid"` and optional `Reranker`. Reuses the existing `graph_stores` entry-point category | shipped (Python) | 0.2 | both | `agentforge-core` (`GraphExpansion` value + config schema), `agentforge` (Retriever extension) |
| **feat-024** | Schema migrations framework — `Migration` value + `Migrator` Protocol + `discover_migrations` helper + per-driver migrators with SHA-256 checksum tracking + `agentforge db migrate` / `migrate-status` CLI. Replaces the monolithic `init_schema()` stand-in across all four persistent-store drivers | shipped (Python) | 0.2 | both | `agentforge-core` (Migration value + Protocol + discovery), `agentforge` (CLI), `agentforge-memory-postgres` / `-sqlite` / `-neo4j` / `-surrealdb` (per-driver migrators) |
| **feat-025** | Neo4jVectorStore + hybrid_search — adds the missing `VectorStore` to `agentforge-memory-neo4j` via Neo4j 5.13+ native `CREATE VECTOR INDEX` + `CREATE FULLTEXT INDEX`. Bundles the SurrealDB native `lexical_search` (feat-022 sister-package follow-up) so every shipped VectorStore passes `run_hybrid_search_conformance` | shipped (Python) | 0.2 | both | `agentforge-memory-neo4j` (new VectorStore), `agentforge-memory-surrealdb` (native lexical_search) |

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

- **No "framework agnostic" abstraction layer.** We don't try to wrap other
  agent / orchestration frameworks. Importing them as tools is fine;
  framework-of-frameworks is not on the roadmap.
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
   `architecture.md` §10 to avoid the version-matrix drift seen in large
   multi-package ecosystems.
