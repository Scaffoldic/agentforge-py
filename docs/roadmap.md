# Roadmap

What's planned but not yet shipped. Feature numbers below match the
canonical specs in [`docs/features/`](./features/) — that's the
single source of truth for feat-NNN identity and scope.

## Numbering note (read this first)

The first three PRs match canonical numbers (PR #1 = feat-001, PR #3
= feat-002, PR #4 = feat-003). PRs #5, #7, #8 shipped under labels
`feat-007`, `feat-009`, `feat-008` respectively but **all three
actually implement portions of canonical feat-005 (Persistence —
`MemoryStore` ABC + drivers)**. The divergence wasn't caught until
after #8 opened. Remediation: "Add mapping + addendum" — no git
history rewrites; canonical
[`feat-005`](./features/feat-005-persistence-and-memory.md)
gains an Implementation section with the mapping; from this PR
onward every feature uses the canonical feat-NNN number.

## In flight

*No features in flight.*

---

## Shipped (Python; TypeScript port pending across the board)

| Canonical | Title | PRs |
|---|---|---|
| [feat-001](./features/feat-001-core-contracts-and-agent.md) | Core contracts + Agent | [#1](https://github.com/Scaffoldic/agentforge-py/pull/1) |
| [feat-002](./features/feat-002-reasoning-strategies.md) | Reasoning strategies | [#3](https://github.com/Scaffoldic/agentforge-py/pull/3) |
| [feat-003](./features/feat-003-llm-provider-abstraction.md) | LLM provider abstraction (Bedrock) | [#4](https://github.com/Scaffoldic/agentforge-py/pull/4) |
| [feat-004](./features/feat-004-tools-system.md) | Tools system — `@tool` decorator + 4 default tools + dispatch enhancements + `FakeTool` | [#10](https://github.com/Scaffoldic/agentforge-py/pull/10) |
| [feat-005](./features/feat-005-persistence-and-memory.md) | Persistence — MemoryStore + sqlite + postgres + neo4j + surrealdb + VectorStore + GraphStore + RAG | [#5](https://github.com/Scaffoldic/agentforge-py/pull/5) (sqlite + RAG, mis-labelled feat-007), [#7](https://github.com/Scaffoldic/agentforge-py/pull/7) (graph + neo4j + surrealdb, mis-labelled feat-009), [#8](https://github.com/Scaffoldic/agentforge-py/pull/8) (postgres, mis-labelled feat-008) |
| [feat-007](./features/feat-007-production-rails.md) | Production rails — `BudgetPolicy` + `RunContext` + `idempotency_key_for` + `RunIdFilter` (shipped under feat-001) + `FallbackChain` cross-provider failover | [#11](https://github.com/Scaffoldic/agentforge-py/pull/11) |
| [feat-008](./features/feat-008-findings-and-output-shapes.md) | Findings & output shapes — `SimpleFinding` / `PatchFinding` / `NarrativeFinding` / `MultiSpanFinding` variants + `Patch` / `Span` helpers + `FindingRenderer` ABC + `RendererRegistry` + 4 built-in renderers (scorecard / patch-applier / markdown / span-table) | [#13](https://github.com/Scaffoldic/agentforge-py/pull/13) |
| [feat-006](./features/feat-006-evaluators-and-benchmarks.md) | Evaluators — `Coverage` / `FormatCompliance` / `RegressionVsBaseline` / `Consistency` deterministic graders + `Agent.run()` evaluator loop + `RunResult.eval_scores` + `agentforge-eval-geval` package (`GEval` engine + `Correctness` / `Faithfulness` / `Groundedness` / `Hallucination` / `Relevance` / `Helpfulness` named judges) | [#14](https://github.com/Scaffoldic/agentforge-py/pull/14) |
| [feat-009](./features/feat-009-observability.md) | Observability — `on_step` wiring + hook fan-out + error isolation + JSON log format + `agentforge-otel` package (`OpenTelemetryHook`, framework root span) | [#15](https://github.com/Scaffoldic/agentforge-py/pull/15) |
| [feat-010](./features/feat-010-module-discovery-and-cli.md) | Module discovery + full CLI — entry-point scan, `ModuleInfo`, `Resolver.list_installed`, `agentforge list/add/remove/swap module` commands, manifest-driven module wiring | [#16](https://github.com/Scaffoldic/agentforge-py/pull/16) (read-only) + (this PR — destructive CLI) |
| [feat-012](./features/feat-012-configuration-system.md) | Configuration system — widened root schema (`agent` + `modules` + `providers` + `output`), `BudgetConfig` (replaces flat `budget_usd`), layered env files, dotted-path overrides, `AGENTFORGE_CONFIG` / `AGENTFORGE_LOG_LEVEL` shortcuts, module-side schema integration, `agentforge config {validate,show,schema}` CLI | [#17](https://github.com/Scaffoldic/agentforge-py/pull/17) |
| [feat-011](./features/feat-011-scaffolding-and-upgrade.md) | Scaffolding & upgrade — `agentforge new` + 6 starter templates (minimal, code-reviewer, patch-bot, docs-qa, triage, research) rendered via Copier, `.agentforge-state/managed-files.lock` + `AGENTFORGE-MANAGED:` marker headers, `agentforge upgrade` (Copier three-way merge), `agentforge fork`/`unfork`/`status` | [#19](https://github.com/Scaffoldic/agentforge-py/pull/19) |
| [feat-017](./features/feat-017-cli-runtime.md) | CLI runtime — `agentforge run` (+ `--replay`/`--record`), `agentforge eval` (JSONL fixtures + JUnit), `agentforge debug` (interactive REPL), `agentforge db {migrate,backup,restore,purge,query}`, `agentforge health` (preflight). Foundations: `MemoryStore.delete` on the ABC, run-recording protocol (reserved `__step`/`__eval`/`__run` categories), `ReplayLLMClient` + `replay_tools`, `build_agent_from_config` helper. Exit codes 0/1/2/3/4/5 locked. | [#20](https://github.com/Scaffoldic/agentforge-py/pull/20) |
| [feat-016](./features/feat-016-testing-framework.md) | Testing framework — `agentforge.testing` namespace (`MockLLMClient` with from_script/deterministic/from_recording, `FakeTool`, `agent_factory`, pytest fixtures, conformance re-exports, `record_llm` with redaction) + `agentforge-testing` package (`GoldenSetRunner`, `assert_snapshot`, `analyze_recording`). | [#21](https://github.com/Scaffoldic/agentforge-py/pull/21) |
| [feat-018](./features/feat-018-safety-and-security-guardrails.md) | Safety guardrails — `InputValidator` / `OutputValidator` / `ToolCallGate` ABCs + `ValidationResult` + `GuardrailPolicy` + audit channel; built-in basics (`prompt_injection_basic`, `pii_redact_basic`, `capability_check`, `allowlist`); `GuardrailEngine` wired into `Agent.run`; conformance harnesses; four vendor sister packages (LLM Guard, Presidio, NeMo, Llama Guard); `RunResult.guardrail_events`. | [#22](https://github.com/Scaffoldic/agentforge-py/pull/22) |
| [feat-019](./features/feat-019-developer-experience-and-ai-rules.md) | Developer experience + AI rules — three-section managed/custom markdown format (`<!-- agentforge:end-managed -->`); `inject_shared_scaffold` post-render hook copies `_shared/` into every new scaffold; 16 runbooks + `AGENTS.md` + `CLAUDE.md` + `.cursorrules` ship Day-1; `agentforge docs` CLI (list / open by stem/number/alias / `--check` drift / `--serve` local HTTP). | [#23](https://github.com/Scaffoldic/agentforge-py/pull/23) |
| [feat-013](./features/feat-013-mcp-integration.md) | MCP integration — `agentforge-mcp` module: `MCPServerClient` (stdio + HTTP/SSE) consumes upstream MCP tool servers via `MCPToolAdapter`s (server-name prefixed); `MCPServer` exposes local tools as MCP; `MCPBridge.from_config` orchestrates from `modules.protocols.mcp`. Production runners scaffolded behind `MCPClientRunner` / `MCPServerRunner` protocols pending live integration tests. | [#24](https://github.com/Scaffoldic/agentforge-py/pull/24) |
| [feat-015](./features/feat-015-pipeline-and-tasks.md) | Pipeline & deterministic tasks — `Task` ABC + `PipelineResult` value in `agentforge-core`; `Pipeline` engine (DAG validation, `asyncio.Semaphore`-bounded parallelism, per-task timeouts, continue/fail error mode) + `PipelineFailure` + `PipelineFindingsTool` built-in; `Agent(pipeline=...)` kwarg + `Agent.run(task, *, context, replay_pipeline)` API; system-prompt addendum; `modules.pipeline:` config block + `build_pipeline_from_config`; `__pipeline` recording category + `load_pipeline_result` replay; `FinishReason` literal extended with `"pipeline"`. | [#25](https://github.com/Scaffoldic/agentforge-py/pull/25) |
| [feat-020 (v0.2 scope)](./features/feat-020-chat-agents.md) | Chat agents v0.2 — `ChatHistoryStore` / `HistoryTruncationStrategy` ABCs + `ChatTurn` / `SessionInfo` / `ChatChunk` / `ChatResponse` value models in `agentforge-core`; `agentforge-chat` package with `ChatSession` (send + stream + idempotency + per-turn/per-session budgets + input/output guardrails + sentence-segmenting buffer-then-stream) and `InMemoryChatHistory` / `SqliteChatHistory` drivers + four truncation strategies (sliding-window, token-budget, summarise-oldest, hybrid); `agentforge-chat-http` package with FastAPI REST + WS + SSE + bearer auth + cross-owner 403 + token-bucket rate limiting; `modules.chat:` config block + `build_chat_session_from_config`. Postgres / Redis drivers, Slack adapter, and real per-token streaming deferred to v0.3 follow-up PRs. | [#26](https://github.com/Scaffoldic/agentforge-py/pull/26) |
| [feat-014](./features/feat-014-a2a-protocol.md) | A2A protocol — canonical `agentforge_core.contracts.auth.AuthPolicy` + `Principal` + `A2ACallError` / `A2AAuthError` / `A2ATimeout` exceptions; `agentforge.auth.EnvBearerAuth` concrete impl; chat-http refactor to the canonical contract; new `agentforge-a2a` package with `agent_call(target, payload, *, peers, budget_usd, budget)` client + bearer / mTLS credentials + `A2AServer` FastAPI app + `A2ABridge` orchestrator + `A2AConfig` schema + run_id / budget header propagation. Production runners scoped behind Protocols with `# pragma: no cover` (same pattern as feat-013 MCP) until the first live integration test lands. | [#27](https://github.com/Scaffoldic/agentforge-py/pull/27) |

For details on what each shipped feature delivered vs. what was
deferred, read the **Implementation status** section at the bottom
of each spec under [`docs/features/`](./features/).

---

## Release sequence

We haven't tagged anything yet. The next release is **v0.1.0**
(everything in the `## Shipped` table above lands in that
tag). The release immediately after is **v0.2.0**, which
contains every Backlog item listed below. After 0.2 the
natural minor sequence continues — v0.3, v0.4, 1.0 —
two-weekly during 0.x per
[ADR-0015](./adr/0015-coordinated-release-train.md).
Spec metadata's `Target version` field is **aspirational**
(set when the spec was written) and may differ from the tag
a feature actually lands in — when they diverge, the tag
wins. The Shipped table above is the durable record.

## v0.2.0 backlog (everything below ships in 0.2)

All remaining work between v0.1.0 and v0.2.0 is in this list.
Each item references its canonical spec under
[`docs/features/`](./features/) or the sub-feat row at the
bottom. Pick one to move into "In flight" when starting; mark
`shipped` here on merge.

### feat-013 follow-up — production MCP runner

**Status: stdio half shipped on the v0.1 → v0.2 line** (see
spec §10 "v0.2 follow-up"). `_SDKClientRunner` and
`_SDKServerRunner` are real implementations against the
upstream `mcp` SDK; framework's first `@pytest.mark.live`
integration test exercises the end-to-end stdio path
(`packages/agentforge-mcp/tests/integration/test_mcp_live.py`).
`pip install agentforge-mcp[mcp]` pulls the SDK as an
optional extra.

What remains for v0.2.1:

- HTTP / SSE server transport for `_SDKServerRunner` — needs
  `mcp.server.streamable_http` + uvicorn wiring.
- Non-text content handling (`ImageContent`,
  `EmbeddedResource`) in `_SDKClientRunner.call_tool`.

### feat-014 follow-ups — production A2A runner + discovery + streaming

**Status: shipped on the v0.1 → v0.2 line** (see spec §10 "v0.2
follow-up"). Three items all landed in one PR:

- **Production HTTP runner** — `_HTTPXClientRunner` +
  `_UvicornServerRunner` now wrap `httpx.AsyncClient` /
  `uvicorn.Server`; v0.1's `# pragma: no cover` stubs are
  replaced. Bodies stay under `# pragma: no cover`; coverage
  proven by `@pytest.mark.live` integration tests.
- **A2A discovery** — `GET /a2a/v1/info` carries the full
  endpoint catalogue (description + JSON-Schema input
  shapes); `agentforge_a2a.discover_peer(peer)` +
  `A2ABridge.discover_all()` + `bridge.peer_info`. Strictly
  client-side; no central registry.
- **Bi-directional streaming** — `POST /a2a/v1/calls/stream`
  returns SSE `A2AChunk` frames; client helper
  `agent_call_stream(...)` yields them. Step-level
  granularity for v0.2.

**v0.3 follow-up: per-token streaming + chunk-kind
unification** — shipped on the v0.1 → v0.3 line (spec §10
"v0.3 follow-up"):

- **Per-token A2A streaming** —
  `A2AServer._stream_call` now drives `Agent.stream(task)`
  and forwards each `StreamingEvent` as an `A2AChunk`. The
  v0.2 hook-append/remove dance is gone; per-token text is
  available end-to-end when the strategy overrides
  `ReasoningStrategy.stream`.
- **Unified `StreamingChunkKind`** — one closed vocabulary
  (`text` / `thinking` / `step` / `tool_call` /
  `tool_result` / `done` / `error`) lives in
  `agentforge_core.values.chat`. `ChatChunkKind` +
  `A2AChunkKind` are aliases.

The per-run hook kwarg on `Agent.run` was **obviated** by
this refactor (no remaining caller) and dropped from scope.

What remains for v0.4+:

- Central A2A registry service (still out of v0.x scope).
- Hardening the `live` CI job to gate merge.
- Overriding `ReasoningStrategy.stream` on built-in
  strategies (`ReActLoop`, etc.).
- TS port.

### feat-020 follow-ups — chat history + adapters + streaming

**Status: shipped on the v0.1 → v0.2 line** (see spec §11
"v0.2 follow-up"). All six items landed in one PR:

- **`agentforge-chat-history-postgres`** — asyncpg-backed
  driver.
- **`agentforge-chat-history-redis`** — Redis-backed driver
  with native TTL.
- **`agentforge-chat-slack`** — Slack reference channel
  adapter.
- **Real per-token streaming** — `ReasoningStrategy.stream()`
  ABC method (non-abstract default for backward compat) +
  `Agent.stream(task)` + `ChatSession.stream()` graduation.
  Unblocks A2A per-token streaming (separate v0.3 PR).
- **Cross-process per-session locking** — `SessionLock`
  Protocol + `RedisSessionLock` with `SET NX PX` + UUID
  fencing + Lua unlock.
- **Provider-aware tokeniser** — `tiktoken_tokeniser` +
  `anthropic_tokeniser` wired into `TokenBudget`.

Remaining for v0.3+:

- A2A per-token streaming using `ReasoningStrategy.stream()`
  — **shipped** in feat-014 v0.3 follow-up.
- Concrete `stream()` overrides on all four built-in strategies
  (`ReActLoop`, `PlanExecuteLoop`, `TreeOfThoughts`,
  `MultiAgentSupervisor`) — **shipped** on the v0.3 polish
  bundle (ReAct) and the v0.3.x strategy follow-ups bundle
  (the other three).
- Multi-cluster Redlock for `RedisSessionLock`.
- Sentence-window streaming output guardrails.
- Migration framework for the Postgres schema.

### feat-009 vendor observability sub-feats

**Status: shipped on the v0.1 → v0.2 line** (see feat-009 spec
§"v0.2 follow-up: vendor backends"). All four packages
landed in one PR, each wrapping its SDK behind the same hook
contract feat-009 v0.1 locked in:

- **`agentforge-langfuse`** — Langfuse trace dashboard
  (LLM-focused). One trace per run, one span per step, scores
  on finish.
- **`agentforge-phoenix`** — Phoenix / Arize dashboard.
  Logs `agent.step` / `agent.tool_call` / `agent.run` events
  to a project namespace.
- **`agentforge-evidently`** — Evidently AI metrics + drift
  monitoring. Per-step rows buffered + a JSON report written
  per run.
- **`agentforge-statsd`** — StatsD metrics emitter. Counters
  + gauges + timings via UDP.

Each uses the runner-Protocol pattern (production runner
under `# pragma: no cover` + in-memory fake in `src/` for
unit tests). SDK is an optional extra; bare install keeps
the package importable without the SDK.

What remains for v0.3+ (per feat-009 spec):

- ~~Child OTel spans (`strategy.iteration`, `llm.call`,
  `tool.<name>`, `evaluator.<name>`).~~ **Shipped** in the
  v0.3 polish bundle (PR #40 — ReActLoop + PlanExecute) and
  the v0.3.x strategy follow-ups bundle (ToT + MultiAgent).
- ~~A2A trace propagation via OTel context.~~ **Shipped** in
  the v0.3 polish bundle (PR #40).
- ~~Content-based PII redaction.~~ **Shipped** in the v0.3
  polish bundle (PR #40).
- Evidently real-time drift dashboards via Cloud.

### Sub-feat backlog (no canonical number yet)

Each becomes its own short spec when picked up; all
targeted for v0.2:

- ~~**GraphRAG-style hybrid retrieval** — combines vector retrieval
  with graph expansion (pull top-k vector matches, then traverse
  outgoing edges to enrich context).~~ — promoted to canonical
  [feat-023](./features/feat-023-graphrag-hybrid.md);
  **shipped** in v0.2 (`GraphExpansion` value +
  `Retriever(graph_expansion=...)` post-retrieve N-hop traversal +
  score-decay merge + dedup, composes orthogonally with
  vector/hybrid + optional reranker). Native single-query
  graph-augmented retrieval inside Neo4j / SurrealDB deferred to
  per-driver follow-ups.
- ~~**Hybrid search** (BM25 + vector fusion) inside the
  `VectorStore` capability vocabulary.~~ — promoted to
  canonical [feat-022](./features/feat-022-hybrid-search.md);
  **shipped** in v0.2 (`VectorStore.lexical_search` ABC
  extension + pure-Python BM25 + `Retriever(mode="hybrid")`
  with RRF fusion + `InMemoryVectorStore` native impl +
  opt-in `run_hybrid_search_conformance` suite). Native
  Postgres (`tsvector` + `ts_rank_cd`) and SQLite (FTS5 +
  `bm25`) lexical paths shipped in the v0.2 follow-up
  bundle. SurrealDB native `lexical_search` (via
  `DEFINE ANALYZER` + `SEARCH ANALYZER ... BM25`) lands
  alongside the new `Neo4jVectorStore` in
  [feat-025](./features/feat-025-neo4j-vector-store.md) so
  every shipped `VectorStore` then passes
  `run_hybrid_search_conformance`.
- **feat-025** —
  [`Neo4jVectorStore`](./features/feat-025-neo4j-vector-store.md)
  + hybrid_search via Neo4j 5.13+ `CREATE VECTOR INDEX` +
  `CREATE FULLTEXT INDEX`. Bundled with the SurrealDB
  native FTS follow-up above.
- ~~**Reranker contract**~~ — promoted to canonical
  [feat-021](./features/feat-021-reranker.md); ABC + default
  SentenceTransformers concrete + `Retriever` integration
  shipped in v0.2. Follow-up v0.2 PR adds the `retrieval:`
  top-level YAML block + `build_retriever_from_config()`
  resolver wiring. Third v0.2 PR ships the vendor reranker
  sister packages (`agentforge-reranker-cohere`, `-voyage`,
  `-mixedbread`) so users swap rerankers in YAML with no
  code changes.
- ~~**Schema migrations** for persistent stores (the
  `init_schema()` opt-in is the v0.1 stand-in; a real migration
  framework lands alongside the first v0.1.0 → v0.2.0 schema delta).~~
  — promoted to canonical
  [feat-024](./features/feat-024-schema-migrations.md);
  **shipped** in v0.2 (`Migration` value + `Migrator` Protocol +
  `discover_migrations` helper + per-driver migrators for
  Postgres / SQLite / Neo4j / SurrealDB +
  `agentforge db migrate` / `migrate-status` CLI). v0.3 polish
  bundle adds template support (`${var}` placeholders in migration
  bodies) so Postgres `vector(N)` + SurrealDB `HNSW DIMENSION N`
  schemas now live under the migration framework too. `down`
  migrations / schema rollback deferred to v0.3+.
