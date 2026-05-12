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

For details on what each shipped feature delivered vs. what was
deferred, read the **Implementation status** section at the bottom
of each spec under [`docs/features/`](./features/).

---

## Backlog (canonical numbers)

These are tracked here so they don't get lost. Full design specs
already exist under [`docs/features/`](./features/); pick one to
move into "In flight" when starting.

- **feat-014** — A2A protocol. See spec under
  [`docs/features/`](./features/).
- **feat-020 v0.3 follow-ups** —
  `agentforge-chat-history-postgres`,
  `agentforge-chat-history-redis`, `agentforge-chat-slack`
  reference adapter, real per-token streaming through the
  strategy loop, cross-process per-session locking
  (Redis-backed), provider-aware tokeniser in `TokenBudget`.

### feat-009 vendor-package sub-feats (deferred)

feat-009 shipped the framework-side observability (hook fan-out,
JSON logs, OTel root span via `agentforge-otel`). The four vendor-
specific dashboard packages from the original spec are deferred —
they each become a small follow-up:

- **`agentforge-langfuse`** — Langfuse trace dashboard (LLM-focused).
- **`agentforge-phoenix`** — Phoenix / Arize dashboard.
- **`agentforge-evidently`** — Evidently AI metrics + drift monitoring.
- **`agentforge-statsd`** — StatsD metrics emitter.

Each wraps its respective SDK behind the same hook contract feat-009
locked in. OTel coverage (every collector that ingests OTLP) covers
the major bases until then.

### Sub-feat backlog (no canonical number yet)

- **GraphRAG-style hybrid retrieval** — combines vector retrieval
  with graph expansion (pull top-k vector matches, then traverse
  outgoing edges to enrich context).
- **Hybrid search** (BM25 + vector fusion) inside the
  `VectorStore` capability vocabulary.
- **Reranker contract** — `Reranker` ABC for cross-encoder reranking
  on top of `VectorStore.search`.
- **Schema migrations** for persistent stores (the
  `init_schema()` opt-in is the v0.1 stand-in; a real migration
  framework lands alongside the first v0.1.0 → v0.2.0 schema delta).
