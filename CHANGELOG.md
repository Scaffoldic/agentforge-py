# Changelog

All notable changes to `agentforge-py` are documented here. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The framework follows a coordinated release train (per ADR-0015): every
release tag bumps every workspace member to the same minor version.

## [Unreleased]

> **Numbering note**: PRs #5, #7, #8 shipped under labels `feat-007`,
> `feat-009`, `feat-008` respectively, but **all three actually
> implement portions of canonical feat-005 (Persistence — `MemoryStore`
> ABC + drivers)** in the parent design workspace at
> `docs/features/feat-005-persistence-and-memory.md`. The divergence
> wasn't caught until after #8 opened. Going forward every feat-NNN
> uses the canonical number; no git history was rewritten. The full
> mapping and deviations are documented in the canonical spec's
> Implementation section. See `docs/roadmap.md` for the policy.

### Changed

- **Project structure made self-contained for AI assistants.** Moved
  the canonical feature catalogue (`docs/features/feat-NNN-*.md`,
  20 specs + README) and per-project state files (`.claude/state/`)
  from the parent design workspace into `agentforge-py`. Added a
  tracked `.claude/CLAUDE.md` whose reading order references only
  files inside this repo — no upward path traversal. `AGENTS.md`
  workflow rules updated: branch `<NNN>` must match an existing
  `docs/features/feat-NNN-*.md` spec; every feature PR updates the
  matching spec's Implementation section; every milestone updates
  `.claude/state/current.md` and appends to `.claude/state/log.md`.
  Background: chore PR #2 had decoupled `agentforge-py` from the
  parent workspace by removing `../../` cross-references but did
  not move the canonical files in. AI sessions reading
  `agentforge-py` couldn't find the catalogue or state record and
  invented feat-NNN numbers from CHANGELOG memory — that's how PRs
  #5/#7/#8 ended up mis-labelled (see canonical `feat-005`'s
  Implementation section for the full mapping). This PR closes the
  loop so future sessions can't trip the same way.

- Documentation made self-contained for the public OSS repo: removed
  `../../` references to a private design workspace from `AGENTS.md`,
  `README.md`, the PR template, and the pre-commit config. Repo
  conventions, install instructions, and the contributor workflow now
  live entirely inside `agentforge-py`.

### Added

- **feat-008 — `agentforge-memory-postgres` (production persistence).**
  Sister package to `agentforge-memory-sqlite` — same locked
  contracts, same conformance suites — but backed by Postgres with
  `asyncpg` and the pgvector extension for real-world scale,
  multi-writer concurrency, and managed-database guarantees (RDS,
  Neon, Supabase, etc.). Closes the postgres deferral from feat-007.

  *New persistence package (`agentforge-memory-postgres`):*
  - **`PostgresMemoryStore`** — claim audit log over a `claims`
    JSONB table with composite indices on `(project, agent)`,
    `run_id`, `category`. Capabilities: `{"transactions"}`. Every
    mutation runs inside an asyncpg transaction.
  - **`PostgresVectorStore`** — semantic search over a `vectors`
    table with a typed `vector(N)` column and a pgvector HNSW index
    (`vector_cosine_ops`). Dimensions pinned at construction.
    `register_vector` is registered on every pooled connection so
    `list[float]` flows through asyncpg's codec as the native
    `vector` type. Capabilities: `{"native_ann"}` declared **only**
    after `init_schema()` provisions the HNSW index — without
    bootstrap the driver still works as a brute-force fallback but
    doesn't claim ANN, per ADR-0009.
  - **Score conversion at the SQL boundary**: pgvector's `<=>`
    returns cosine *distance* in [0, 2] (0 = identical,
    1 = orthogonal, 2 = anti-correlated); the locked contract
    requires similarity in [0, 1]. The driver emits
    `GREATEST(0.0, 1.0 - (embedding <=> $1))` so cross-driver scores
    are directly comparable.
  - **Metadata filter** is conjunctive equality via
    `metadata @> $2::jsonb` (Postgres JSONB containment); empty
    filter `{}` matches all rows.
  - **Internal `PostgresRunner` protocol** + production
    `_AsyncpgPoolRunner` wrapping `asyncpg.create_pool`
    (`min_size=1`, `max_size=10` by default; pool acquired per
    call). Tests inject a `PostgresFakeRunner` in conftest that
    interprets the SQL vocabulary and routes operations to
    `InMemoryStore` / an in-process vector dict — no Postgres
    required for CI. Same pattern feat-009 proved out for Neo4j and
    SurrealDB.
  - **`init_schema()`** is opt-in and idempotent on both stores
    (`CREATE EXTENSION / TABLE / INDEX IF NOT EXISTS`). No
    migration framework yet — the schema shape is pinned for v0.1.
  - **All SQL is parameterised via asyncpg's numbered `$1, $2, …`
    placeholders.** Schema-bootstrap and filter-builder f-strings
    reference only framework table-name constants (never user
    input); S608 / B608 noqa annotations explicitly say so. The
    `vector(N)` type literal is the only place a value is
    interpolated, and it's validated as an `int` first since
    pgvector forbids parameter binding for that position.
  - **Live integration tests** exercise both conformance suites
    against a real Postgres + pgvector, gated on
    `RUN_LIVE_POSTGRES=1`. Docker-compose dev stack ships
    `pgvector/pgvector:pg16`. CI does not run these (the
    `@pytest.mark.live` marker is excluded by `pytest -m "not
    live"`).
  - 20 unit tests (6 memory + 14 vector) all green; both
    `run_memory_conformance` and `run_vector_conformance` pass via
    the fake runner.

  *Workspace + CI wiring:*
  - Package added to root pyproject (workspace member, `[tool.uv.sources]`,
    coverage source, pytest testpaths).
  - New mypy override block for `asyncpg.*` and `pgvector.*` (neither
    SDK ships `py.typed`).
  - `.github/workflows/ci.yml` and `.pre-commit-config.yaml` extended
    in lockstep (mypy, bandit, pytest unit) per the rule established
    in feat-009.

- **feat-009 — `GraphStore` ABC + Neo4j and SurrealDB drivers.** Adds
  the third locked Tier-1 contract — graph traversal — alongside
  the existing `MemoryStore` (claim audit log) and `VectorStore`
  (similarity search) ABCs. Unlocks knowledge-graph agents,
  multi-hop reasoning over a corpus, and ontology-driven planning
  without compromising the minimalism of the other contracts.

  *New core contracts (`agentforge-core`):*
  - **`GraphStore` ABC** under `agentforge_core.contracts.graph_store`.
    Methods: `add_node`, `add_edge`, `get_node`, `get_edges`, `match`,
    `traverse`, `delete_node`, `delete_edge`, `close`, `capabilities`,
    `supports`. Distinct from `MemoryStore` and `VectorStore` because
    graph traversal — multi-hop walks, pattern matching — doesn't
    fit metadata-filter or cosine-similarity shapes.
  - **`GraphNode`**, **`GraphEdge`**, **`GraphSegment`**, **`GraphPattern`**,
    **`Path`** frozen Pydantic value types. `GraphPattern` enforces
    `len(node_filters) ∈ {0, len(segments) + 1}`; `Path` enforces
    `len(edges) == len(nodes) - 1`.
  - **`run_graph_conformance(store)`** suite in
    `agentforge_core.testing`. Round-trip, idempotent upsert, get_edges
    directionality, single-segment match, depth-bounded traverse,
    cascade delete semantics, capability honesty.

  *New runtime helpers (`agentforge`):*
  - **`InMemoryGraphStore`** — process-local reference impl. Dict +
    adjacency list, BFS traversal with cycle avoidance, brute-force
    pattern walk. Passes `run_graph_conformance` from day one.
  - **`Agent(graph_store=...)`** constructor kwarg threads a
    `GraphStore` through `RuntimeContext.graph_store` so strategies
    can do multi-hop reasoning via
    `get_runtime(state).graph_store.traverse(...)` without the caller
    threading the store manually. Existing `Agent(...)` constructions
    keep working — the field is optional.
  - 6 Hypothesis property tests against `InMemoryGraphStore` exercise
    arbitrary graph shapes (round-trip, idempotent upsert, traverse
    depth bound, cascade delete, Path invariants).

  *New persistence package (`agentforge-memory-neo4j`):*
  - **`Neo4jGraphStore`** — full GraphStore contract over Neo4j 5.x
    via the official `neo4j` async driver. Models the framework's
    dynamic-label model with a marker label `:AfNode` + `_af_labels`
    property (Cypher can't parameterise label names); same pattern
    for edges (`:AF_EDGE` + `_af_edge_type`). Compiles multi-segment
    `GraphPattern`s to native Cypher with parameterised WHERE
    clauses. `traverse()` uses Cypher's variable-length `*1..N`.
    Capabilities: `{"transactions", "cypher", "fulltext"}`.
  - **`Neo4jMemoryStore`** — MemoryStore over `:Claim` nodes.
    Supersede chains also write `[:SUPERSEDES]` edges so graph
    queries can traverse claim history.
  - `init_schema()` is opt-in (idempotent constraints + indexes).
  - Docker-compose dev stack ships in the package. Live integration
    tests gated on `RUN_LIVE_NEO4J=1`; CI does not run them. Unit
    tests use a `GraphFakeRunner` / `MemoryFakeRunner` in conftest
    that interpret the Cypher vocabulary the driver emits.

  *New persistence package (`agentforge-memory-surrealdb`):*
  - AgentForge's first multi-modal persistence package. SurrealDB
    supports documents, vectors, and graphs natively; the package
    implements all three locked contracts against one
    `surrealdb.AsyncSurreal` client.
  - **`SurrealGraphStore`** — GraphStore via native
    `RELATE src->edge_table->dst` syntax. `match()` and `traverse()`
    walk client-side via repeated `get_edges` queries — correct,
    portable, easily testable. Capabilities:
    `{"transactions", "surrealql", "vector", "live_query"}`.
  - **`SurrealVectorStore`** — VectorStore. `init_schema()`
    provisions an HNSW index; the driver declares `{"native_ann"}`
    only after, with a brute-force fallback otherwise.
  - **`SurrealMemoryStore`** — MemoryStore over `af_claim` records.
  - All SurrealQL strings are module-level constants composed of
    framework-defined table names (never user input); S608 lint
    warnings explicitly noqa'd with that rationale.
  - Docker-compose dev stack (SurrealDB v2). Live integration tests
    gated on `RUN_LIVE_SURREAL=1`. Unit tests use a multi-modal
    `SurrealFakeRunner` in conftest.

  *Agent integration:*
  - `RuntimeContext.graph_store: GraphStore | None` added.
  - `Agent.close()` now also `await graph_store.close()` so external
    drivers release their connections cleanly.

  *CI:*
  - Both new packages added to `.github/workflows/ci.yml` (mypy,
    bandit, pytest unit). mypy override blocks added for `neo4j.*`
    and `surrealdb.*` since both SDKs ship without `py.typed`.

- **feat-007 — Persistent memory + vector search + RAG.** Lifts agents
  from "process-local memory only" to "persistent state across runs"
  and adds semantic retrieval so agents can ground answers in indexed
  documents. Validates the three-tier package model end-to-end.

  *New core contracts (`agentforge-core`):*
  - **`VectorStore` ABC** under `agentforge_core.contracts.vector_store`.
    Methods: `upsert`, `search`, `delete`, `close`, `dimensions`,
    `capabilities`, `supports`. Distinct from `MemoryStore` (claim
    audit log) — the shapes don't unify cleanly. Cosine scores
    normalised to `[0, 1]` (1 = identical direction; 0 = orthogonal-
    or-anti-correlated).
  - **`VectorItem`** and **`VectorMatch`** frozen Pydantic value types.
    Vectors are `tuple[float, ...]` for immutability + hashability.
  - **`run_vector_conformance(store)`** suite in
    `agentforge_core.testing`. Pytest-free; verifies the locked
    invariants every driver must respect: dimensions positive,
    upsert is write-through, results sorted desc, exact-match
    scores ≈ 1.0, dimension mismatch raises ValueError, metadata
    filter is conjunctive AND, delete returns actual count.

  *New runtime helpers (`agentforge`):*
  - **`InMemoryVectorStore`** — process-local reference impl. Brute-
    force cosine over an `OrderedDict`. L2-normalises on upsert so
    search math is a plain dot product. Suitable for tests, demos,
    small RAG corpora; production swaps to a persistent driver.
  - **`Retriever`** — high-level adapter wrapping `VectorStore` +
    `EmbeddingClient`. `add_documents(texts, *, ids=None,
    metadata=None, batch_size=32)` with auto-ULID generation.
    `retrieve(query, *, top_k=None, filter_metadata=None)` embeds
    the query and forwards to `VectorStore.search`. Constructor
    enforces dimension parity between store and embedder up-front.
  - **`Agent(retriever=...)`** kwarg threads a `Retriever` through
    `RuntimeContext.retriever` so strategies can do RAG via
    `get_runtime(state).retriever.retrieve(...)` without the caller
    having to thread store/embedder manually. Existing `Agent(...)`
    constructions keep working — the field is optional.

  *New persistence package (`agentforge-memory-sqlite`):*
  - **`SqliteMemoryStore`** — persistent `MemoryStore` over
    `aiosqlite`. Single-table schema with composite indices on
    `(project, agent)`, `run_id`, and `category`. JSON payload
    serialisation, supersede() preserves history. `from_path(path)`
    handles `:memory:` and filesystem databases; async context
    manager closes the connection.
  - **`SqliteVectorStore`** — persistent `VectorStore` over
    `aiosqlite`. Vectors stored as fixed-width float64 BLOBs
    (`struct.pack '<Nd'`), brute-force cosine scan in Python
    (~10k vectors fine; v0.2 will add an opt-in `sqlite-vec`
    extension path declared via the `"native_ann"` capability).
    Dimensions pinned per database in a `vector_meta` table — re-
    opening with a different value raises `ValueError` rather than
    silently corrupting.
  - Both stores pass the framework's conformance suites verbatim.

  *Tests:* 89 new unit tests covering value-type validation,
  ABC default behaviour, the in-memory impl, the `Retriever`
  adapter (auto-ULID, batching, length-mismatch validation,
  metadata forwarding), `SqliteMemoryStore` (conformance + edge
  cases + persistence across reconnects), `SqliteVectorStore`
  (conformance + dimension pinning + BLOB roundtrip), and Agent
  retriever wiring. Plus 7 Hypothesis property tests for vector
  invariants (cosine direction-only, dimension enforcement, sort
  order, bounded result count, delete round-trip) and a 3-test
  integration suite that wires the full RAG pipeline end-to-end
  (Embedder → VectorStore → Retriever → Agent).

  *Postgres deferred to feat-008.* SQLite covers the v0.1 use
  cases (development, single-host deployments, small-to-medium
  RAG corpora). A production Postgres driver with `pgvector` and
  `asyncpg` ships in feat-008 once we have actual deployment plans.

- **feat-003 — `agentforge-bedrock` provider + capability extensions.**
  First concrete LLM provider for AgentForge. AWS Bedrock support
  (Anthropic, Titan, Cohere) over the Converse / ConverseStream /
  InvokeModel APIs, plus the cross-provider extensions every future
  driver (`-anthropic`, `-openai`, `-azure`, …) consumes.

  *Core contract extensions (chunk 1):*
  - **Optional `LLMClient` methods** (default-raise so the contract
    stays additive per ADR-0009): `call_with_cache`,
    `call_with_thinking`, `stream() -> AsyncIterator[StreamChunk]`.
  - **Value types**: `StreamChunk` (kind: text / thinking /
    tool_call / stop), `EmbeddingResponse`.
  - **`EmbeddingClient` ABC** under `agentforge_core.contracts.embedding`.
  - **Provider error hierarchy**: `RateLimitError`,
    `AuthenticationError`, `ModelNotFoundError`, `ServiceError`,
    `TimeoutError` under `ProviderError` (the framework's
    `TimeoutError` deliberately does not subclass `OSError`).
  - **Resolver helpers**: `@register_provider("name")` and
    `@register_embedding_provider("name")` so chat and embedding
    drivers can share a provider name in different categories.

  *`agentforge-bedrock` package (chunks 2–5):*
  - **`BedrockClient`** — registered as `providers/bedrock`. Async
    via `aioboto3` per ADR-0014. Implements `call`,
    `call_with_cache` (cachePoint blocks at message breakpoints),
    `call_with_thinking` (Anthropic extended thinking via
    `additionalModelRequestFields.thinking`; reasoningContent
    blocks dropped from public answer), and `stream()` over
    ConverseStream (text / thinking / tool_use deltas normalised
    into `StreamChunk`s, terminal stop chunk carrying usage and
    cost). Plus `accumulate_stream()` — adapter that consumes a
    stream into a single `LLMResponse`. Capabilities:
    `{"tools", "json_mode", "caching", "thinking", "streaming"}`.
  - **`BedrockEmbeddingClient`** — registered as
    `embeddings/bedrock`. Detects the model family from the id
    prefix: Titan loops one text per `InvokeModel` call;
    Cohere uses the native batched shape. `dimensions()` resolved
    from `prices.json` at construction for storage sizing.
  - **Cross-region inference profile support** — `us.`, `eu.`,
    `apac.`, `global.` model id prefixes pass through to Bedrock
    unchanged. Pricing strips the prefix transparently so the
    table only needs the base model row.
  - **Cost calculation** — JSON-backed per-model price table.
    Unknown models log once and report `cost_usd=0` rather than
    crashing. Add new models by editing `prices.json`; no code
    release needed.
  - **Error mapping + bounded backoff** — botocore `ClientError`
    codes map to `ProviderError` subclasses (HTTP-status fallback
    for unknown codes); `with_retry` retries `RateLimitError`,
    `ServiceError`, `TimeoutError` with exponential backoff +
    jitter, capped at 30s and `max_retries` attempts. Auth and
    not-found errors propagate immediately. Streams are NOT
    retried (partial output already published).
  - **Live integration test** opt-in via `RUN_LIVE_BEDROCK=1`,
    targeting `us.anthropic.claude-haiku-4-5-20251001-v1:0` by
    default. Skipped from CI; runs locally against
    `~/.aws/credentials`.

  *Agent integration (chunk 6):*
  - `Agent(model="bedrock:<model-id>")` resolves through the
    `providers` resolver category. Provider name is surfaced in a
    clear `ModuleError` if the package is not installed
    (`Install agentforge-<provider>`).

  *Conformance:*
  - **`run_embedding_conformance(client)`** — shared suite under
    `agentforge_core.testing` covering the locked
    `EmbeddingClient` invariants. Pytest-free so any test runner
    can drive it.

  *Tests:* 119 new unit tests + 2 integration tests + 5 Hypothesis
  property tests covering cost-calculation linearity and
  cross-region prefix invariance. 2 opt-in live Bedrock tests
  (gated on `RUN_LIVE_BEDROCK=1`). 464 total tests; ~96% coverage
  on the new package.

- **feat-002 — Reasoning strategies (all four stable).** All four
  reasoning loops ship as production-stable in `agentforge.strategies`
  (no experimental package per ADR-0008).

  *Shared infrastructure (chunk 1):*
  - **`RuntimeContext`** — frozen per-run execution context (LLM,
    tools, memory, budget, system prompt) bound to
    `state.metadata[RUNTIME_KEY]` by `Agent.run()`. Lives in
    `agentforge` (not `agentforge-core`) to avoid the circular import
    between contracts and runtime concerns.
  - **`StrategyBase`** — abstract base every shipped strategy
    inherits, providing `_check_guardrails`, `_record_step`, and
    `_call_llm` (guardrail-check → LLM call → cost commit → step
    record). The conformance suite verifies via AST inspection that
    every concrete strategy class invokes `_check_guardrails` (or
    `_call_llm`) inside its main loop.
  - **`get_runtime(state)`** helper with clear errors when a strategy
    is invoked outside `Agent.run()`.
  - **`FakeLLMClient`** in `agentforge._testing` — scripted-response
    LLM client driving every feat-002 unit & integration test.
  - **`run_strategy_conformance`** in `agentforge_core.testing` — the
    suite every shipped (and third-party) strategy must pass.

  *`ReActLoop` (chunk 2):* modern reasoning + acting loop with
  structured tool calls. Terminates on `stop_reason="end_turn"` (no
  tool_calls in the response — the modern signal-based approach;
  feature-flagged `Final Answer:` parsing is reserved for
  experimental-only opt-in). Constructor surface locked at v0.1:
  `ReActLoop(*, max_iterations=None)`. Registered as
  `strategies/react`.

  *`PlanExecuteLoop` (chunk 3):* typed plan + parallel execution.
  Phases: PLAN (structured `Plan`/`PlanStep` Pydantic schema, cycles
  & dangling deps caught at parse time) → EXECUTE (topological
  batches, `asyncio.Semaphore`-capped concurrency) → SYNTHESIZE.
  Re-plans on parse / execution failure up to `max_replans`.
  Constructor: `PlanExecuteLoop(*, max_parallel_steps=4,
  replan_on_failure=True, max_replans=1)`. Registered as
  `strategies/plan-execute`.

  *`TreeOfThoughts` (chunk 4):* beam-search reasoning with scored
  branches. Phases: GENERATE (`branch_factor` candidates) → SCORE
  (Pydantic `_BranchScoreList`, 0..1) → PRUNE (`score_threshold` +
  optional top-K via `beam_width`) → EXPAND (recurse to `depth`) →
  SYNTHESIZE (best path → final answer). Budget-aware graceful
  degradation: estimates next-level cost from running average and
  synthesises early instead of crashing if it would exceed the
  remaining budget. `scorer="judge"` falls back to `"self"` for v0.1
  (cheap-judge model lands in feat-006). Constructor:
  `TreeOfThoughts(*, branch_factor=3, depth=2, score_threshold=0.5,
  scorer="self", beam_width=None)`. Registered as `strategies/tot`.

  *`MultiAgentSupervisor` (chunk 5):* supervisor delegates subtasks
  to a configurable set of worker strategies. Phases: DELEGATE
  (Pydantic `_DelegationPlan`, unknown workers dropped with logged
  warning) → EXECUTE WORKERS (parallel under
  `asyncio.Semaphore(max_parallel_workers)`; each worker gets a
  fresh `AgentState`, a *proportional* `BudgetPolicy` cut from the
  parent's remaining USD, and the shared parent `MemoryStore`;
  per-worker spend reconciled into the parent budget on success
  *and* failure; worker exceptions caught and recorded as a
  `delegate` step with `error`) → AGGREGATE (synthesise outputs).
  Workers can be any `ReasoningStrategy`, including another
  `MultiAgentSupervisor` (recursive composition). Constructor:
  `MultiAgentSupervisor(*, workers, max_parallel_workers=4,
  max_rounds=1, worker_descriptions=None)`. Registered as
  `strategies/multi-agent`.

  *Cross-strategy guarantees (chunk 6):* Hypothesis property tests
  prove the budget invariant holds across all four shipped
  strategies: every run either terminates cleanly with
  `spent_usd <= cap + max_call_cost` or raises `BudgetExceeded` /
  `GuardrailViolation` (one in-flight call may push spend over the
  cap; subsequent calls are blocked). Strategies are exercised over
  randomized cap × per-call-cost matrices.

  *Tests:* 300+ unit + integration + property tests covering
  constructor validation, happy paths, parse-error fallback,
  code-fence stripping, parallel-execution semantics, budget
  graceful degradation, and recursive composition. ~96% line +
  branch coverage on the diff.

- Repository bootstrap: uv workspace, ruff/mypy/pytest/coverage tooling,
  GitHub Actions CI, pre-commit hook, Apache 2.0 license, AGENTS.md,
  README, member package skeletons (`agentforge-core`, `agentforge`).

- **feat-001 — Core contracts & `Agent` orchestrator.** The
  foundational layer of AgentForge.

  *agentforge-core (Tier 1):*
  - **Locked contracts (ABCs + Protocol):** `LLMClient`, `Tool`,
    `ReasoningStrategy`, `MemoryStore`, `Evaluator` ABCs plus the
    `Finding` Protocol. Adding a method to any of these is a major
    version bump (per ADR-0007).
  - **Locked value types (frozen Pydantic v2):** `Message`,
    `ToolCall`, `ToolSpec`, `TokenUsage`, `LLMResponse`, `Step`,
    `AgentState`, `RunResult`, `Claim`, `EvalResult`. Closed
    `Literal` enums for `MessageRole`, `StopReason`, `StepKind`,
    `FinishReason`. ULID-defaulted `Claim.id` and run ids.
  - **Production rails:** `BudgetPolicy` (USD / token / iteration /
    error-streak caps with `reserve` / `commit` / `release_reservation`
    semantics), `RunContext` + `current_run()` ContextVar +
    `bind_run` / `reset_run` lifecycle, `RunIdFilter` (idempotent
    install / uninstall) for stdlib-logging correlation, full
    exception hierarchy.
  - **Resolver:** in-process module registry (`Resolver`,
    `@register` decorator) and `parse_model_string` for the
    `<provider>:<model_id>` syntax.
  - **Testing utilities:** `agentforge_core.testing.run_memory_conformance`
    — the shared conformance suite every memory driver must pass.

  *agentforge (Tier 2 — default runtime):*
  - **`Agent` orchestrator** with the locked constructor surface
    per feat-001 §4.2 and the lifecycle defined in ADR-0010
    (bind run_id → strategy.run → fire on_finish → produce
    RunResult). Async context manager.
  - **`InMemoryStore`** — process-local `MemoryStore` reference impl
    used by default when no persistence module is configured.
  - **Configuration loader** with env-var interpolation
    (`${VAR}`, `${VAR:default}`, `${VAR:?error}`, `$$` → `$`),
    Pydantic schema validation, and `extra="forbid"` rejection of
    unknown sections (per ADR-0013).

  *Tests:* 192 unit + integration + conformance + Hypothesis
  property tests. 94.28% line + branch coverage on the diff.

### Fixed

- Repository placeholder URLs replaced with the live remote
  (`github.com/Scaffoldic/agentforge-py`).
- Workspace `pyproject.toml` migrated from deprecated
  `[tool.uv] dev-dependencies` to `[dependency-groups] dev`; root
  declares workspace members as dependencies so `uv sync` installs
  them into the shared venv.
- Pre-commit `bandit` hook now passes `-c pyproject.toml` so it
  reads `[tool.bandit]` (skips B101 — assert is the legitimate
  conformance-suite mechanism).

[Unreleased]: https://github.com/Scaffoldic/agentforge-py/compare/HEAD...HEAD
