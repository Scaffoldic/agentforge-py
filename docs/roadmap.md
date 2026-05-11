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
| [feat-010](./features/feat-010-module-discovery-and-cli.md) | Module discovery (runtime + read-only CLI) — `importlib.metadata.entry_points` scan, `ModuleInfo`, `Resolver.list_installed`, `agentforge list modules` command | (this PR) |

For details on what each shipped feature delivered vs. what was
deferred, read the **Implementation status** section at the bottom
of each spec under [`docs/features/`](./features/).

---

## Backlog (canonical numbers)

These are tracked here so they don't get lost. Full design specs
already exist under [`docs/features/`](./features/); pick one to
move into "In flight" when starting.

- **feat-011 through feat-020** — see specs under
  [`docs/features/`](./features/).

### feat-010 destructive-CLI sub-feat (deferred)

feat-010 shipped the runtime side (entry-point discovery, `Resolver.
list_installed`) plus the read-only `agentforge list modules` CLI.
The destructive CLI commands (`add module X`, `swap memory sqlite
postgres`, `remove module X`) depend on feat-012 (Configuration
system) for manifest application + per-module config-schema
validation, and ship as a follow-up sub-feat alongside / right
after feat-012.

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
