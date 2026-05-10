# Roadmap

What's planned but not yet shipped. Feature numbers below match the
canonical specs in
`/Users/khemchandjoshi/MbytesWorkspace/ai-agents/docs/features/`
(the parent design workspace) — that's the single source of truth
for feat-NNN identity and scope.

## Numbering note (read this first)

The first three PRs in this repo (PR #1 = feat-001, PR #3 =
feat-002, PR #4 = feat-003) match canonical numbers. PRs #5, #7, #8
shipped under labels `feat-007`, `feat-009`, `feat-008` respectively
but **all three actually implement portions of canonical feat-005
(Persistence — `MemoryStore` ABC + drivers)**. The divergence wasn't
caught until after #8 opened. We adopted "Add mapping + addendum" as
the remediation:

- **No git history rewrites.** PR titles, branch names, and commit
  messages stand.
- **Canonical feat-005 spec gains an Implementation section** with a
  mapping table and the deviations recorded. See
  `docs/features/feat-005-persistence-and-memory.md` Implementation
  status (last section).
- **From this PR onward**, every feature uses the canonical
  feat-NNN number, and every PR updates the matching spec's
  Implementation section before merge.

## In flight

*No features in flight.*

---

## Shipped (Python; TypeScript port pending across the board)

| Canonical | Title | PRs |
|---|---|---|
| feat-001 | Core contracts + Agent | [#1](https://github.com/Scaffoldic/agentforge-py/pull/1) |
| feat-002 | Reasoning strategies | [#3](https://github.com/Scaffoldic/agentforge-py/pull/3) |
| feat-003 | LLM provider abstraction (Bedrock) | [#4](https://github.com/Scaffoldic/agentforge-py/pull/4) |
| feat-005 | Persistence — MemoryStore + sqlite + postgres + neo4j + surrealdb + VectorStore + GraphStore + RAG | [#5](https://github.com/Scaffoldic/agentforge-py/pull/5) (sqlite + RAG, mis-labelled feat-007), [#7](https://github.com/Scaffoldic/agentforge-py/pull/7) (graph + neo4j + surrealdb, mis-labelled feat-009), [#8](https://github.com/Scaffoldic/agentforge-py/pull/8) (postgres, mis-labelled feat-008) |

For details on what each shipped feature delivered vs. what was
deferred, read the **Implementation status** section at the bottom
of each canonical `docs/features/feat-NNN.md` spec.

---

## Backlog (canonical numbers, no design yet)

These are tracked here so they don't get lost. Full designs already
exist in `docs/features/feat-NNN.md`; they get pulled into "In
flight" when prioritised.

- **feat-004 — Tools system.** `Tool` ABC was shipped under feat-001
  but the full tool registry, parallel tool calls, tool guard rails,
  and tool result handling spec lives in feat-004.
- **feat-006 — Evaluators & benchmarks.** `Evaluator` ABC was shipped
  under feat-001; the full eval framework (closes `scorer="judge"`
  placeholder in feat-002's `TreeOfThoughts`) is feat-006.
- **feat-007 — Production rails.** Cost budget (partially shipped via
  `BudgetPolicy`), fallback chain (NOT shipped), `run_id` propagation
  (partially shipped), idempotency (NOT shipped). The full feat-007
  scope remains.
- **feat-008 — Findings & output shapes.** `Finding` Protocol +
  variants (Simple, Patch, Narrative, MultiSpan) + renderers. Spec
  exists; not yet implemented. **Note:** PR #8 was *labelled*
  feat-008 but actually implemented part of feat-005.
- **feat-009 — Observability.** Structured logging + OpenTelemetry +
  dashboard exporters. Spec exists; not yet implemented. **Note:**
  PR #7 was *labelled* feat-009 but actually implemented part of
  feat-005.
- **feat-010 — Module discovery & CLI.** Entry-point auto-loader so
  `pip install agentforge-X` enables `Agent(model="X:…")` without
  explicit import.
- **feat-011 through feat-020** — see canonical specs in
  `docs/features/`.

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
