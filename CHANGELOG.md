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

### Added

- **feat-009 — Observability (OTel only).** Ships the framework-
  side observability wiring + the `agentforge-otel` package. Vendor-
  specific backends (Langfuse, Phoenix, Evidently, StatsD) are
  deferred to follow-up sub-feats — the spec's thesis backs this:
  OTel is the wire format, every major collector ingests OTLP.

  *Runtime fan-out + on_step wiring (`agentforge`):*
  - **`on_step` actually fires now**. The kwarg was accepted under
    feat-001 but never invoked — closes that gap.
  - **List-of-hooks fan-out**: `on_step` / `on_finish` accept a
    single callable OR a list. Type aliases `StepHooks` /
    `FinishHooks`. Internally normalised; fires in registration
    order.
  - **Error isolation**: hook exceptions logged at WARN via
    `agentforge.observability` and swallowed. Spec §4.3:
    "Observability must never break the run."
  - **Async hooks supported** for both `on_step` and `on_finish`.
  - **Steps fire on error paths** too (inside `try/finally`).

  *JSON log format (`agentforge-core`):*
  - **`JsonFormatter`** — one JSON object per record with `ts`,
    `level`, `logger`, `msg`, `run_id`, and any `extra` fields
    passed through.
  - **`install_json_formatter` / `uninstall_json_formatter`** —
    idempotent install of a `StreamHandler` with `JsonFormatter`
    on the root (or any) logger.
  - `Agent.__init__` installs it when `logging.format == "json"`
    in the config.

  *OTel API surface (`agentforge-core`):*
  - Adds `opentelemetry-api>=1.27` as a runtime dependency.
    Degrades to no-op spans when no SDK is installed.
  - New `agentforge_core/observability/tracing.py` with
    `get_tracer()` and `SCOPE_NAME = "agentforge"`.
  - `Agent.run` opens a root `agent.run` span with attributes for
    run_id, task, finish_reason, cost, tokens, duration, and
    step count.

  *New package — `agentforge-otel`:*
  - **`OpenTelemetryHook(endpoint=, service_name=, sample_rate=,
    redact_fields=)`** — construction installs the OTel SDK tracer
    provider + OTLP gRPC exporter + `TraceIdRatioBased` sampler.
    Idempotent; respects existing user-installed providers.
  - Satisfies both `on_step` and `on_finish` via `__call__` type
    dispatch. Step events add per-step attributes to the active
    span; tool-call events add `agentforge.tool.*` with key-based
    arg redaction. Finish handling emits an `agentforge.observability`
    INFO summary.
  - Default `redact_fields`: `api_key`, `password`, `secret`,
    `token`, `authorization`. Override per-instance.
  - Entry-point registration under `agentforge.hooks` for
    feat-010 resolver lookup.

  *What's NOT yet shipped:* the four vendor packages
  (`agentforge-langfuse`, `agentforge-phoenix`,
  `agentforge-evidently`, `agentforge-statsd`); `strategy.iteration`
  / `llm.call` / `tool.<name>` / `evaluator.<name>` as proper OTel
  child spans (current implementation flattens them as events on
  the root span); A2A trace propagation; content-based PII
  redaction; TypeScript port. See feat-009's Implementation
  section for the full list.

  *Knock-on docs:* `feat-004` (Tools) had a "Cost attribution per
  tool — feat-009 (Observability)" forward-tense item in
  "What's not yet implemented"; now reflects that feat-009 has
  shipped per-tool cost attribution via the OTel hook's
  `agent.tool_call` events.

- **feat-006 — Evaluators & benchmarks.** Ships the four
  deterministic graders, the LLM-judge engine + six named judge
  graders (new `agentforge-eval-geval` package), and the
  runtime integration that runs evaluators after every
  `Agent.run()` with budget gating.

  *New in `agentforge` (runtime):*
  - **`RunResult.eval_scores: tuple[EvalResult, ...]`** — new
    field, defaults to `()`. Preserves configured evaluator
    order. Adding a field with a safe default is a minor bump
    under ADR-0007.
  - **`Agent._run_evaluators`** runs after the strategy returns,
    before `on_finish`. Each evaluator is gated on
    `budget.remaining_usd()` against its `cost_estimate_usd`;
    skipped graders are logged at WARN via the
    `agentforge.evaluators` logger and don't appear in
    `eval_scores`. Evaluators receive the `RunResult` as `finding`
    and a context dict carrying `task`, `state`, `budget`.
  - **`agentforge.eval.Coverage`** — fraction of expected items
    found in the output (case-insensitive substring by default;
    pass `extractor=` for structured output).
  - **`agentforge.eval.FormatCompliance`** — three modes:
    `regex=`, `pydantic_model=`, `json_parseable=True`. Score is
    binary (1.0 / 0.0).
  - **`agentforge.eval.RegressionVsBaseline`** — loads a JSONL
    baseline file (`{"task": ..., "expected": ...}` per line);
    `exact` or `structural` modes; `no_baseline` label with
    NaN score when no baseline entry matches.
  - **`agentforge.eval.Consistency`** — N re-runs via a caller-
    supplied `runner: Callable[[str], Awaitable[Any]]`; score is
    fraction-of-agreement. Custom `matcher=` for fuzzy compare.
  - All four declare `cost_estimate_usd = 0.0` — they run on every
    call regardless of budget.

  *New package — `agentforge-eval-geval`:*
  - **`GEval`** engine — generic LLM-judge `Evaluator`. Rubric is
    a dict (or YAML) with `criteria`, `scoring`, optional
    `examples`, optional `inputs` (context keys to inject).
    Parses judge responses defensively; commits judge cost to
    the run's `BudgetPolicy` via `contextlib.suppress` (best-
    effort, never voids the result).
    `GEval.from_rubric_file(path, judge=...)` loads YAML rubrics.
  - Six **named graders** subclassing `GEval` with shipped
    rubrics: `Correctness`, `Faithfulness`, `Groundedness`,
    `Hallucination`, `Relevance`, `Helpfulness`. Each accepts a
    `judge: LLMClient` plus optional context-field overrides
    (`ground_truth_field`, `sources_field`).
  - Six versioned YAML rubrics shipped inside the package
    (`src/agentforge_eval_geval/rubrics/*.yaml`), force-included
    in the wheel via hatchling.
  - Entry-point registration under `agentforge.evaluators` for
    every named grader + `geval` — feat-010 (module discovery)
    will resolve `Agent(evaluators=["correctness", ...])` by
    name when it ships.

  Workspace: `agentforge-eval-geval` added to root `pyproject.toml`
  workspace deps + sources + testpaths + coverage source. CI
  workflow and `.pre-commit-config.yaml` extended in lockstep
  with the new mypy / bandit / pytest paths.

  *Deviations from spec §4:* variant graders are constructible
  Python objects (not yet resolved by name — needs feat-010);
  `RunResult.eval_scores` is a tuple, not a flat dict; eval
  config from `agentforge.yaml` is deferred to feat-012; the
  `agentforge eval` CLI is deferred to feat-017. See feat-006's
  spec for the full deviation list and what's not yet shipped.

  *Knock-on docs change:* feat-002's runbook is updated — the
  ToT `scorer="judge"` note no longer says "until feat-006
  lands"; instead it explains that feat-006 shipped the post-run
  evaluator surface but ToT's in-strategy branch scoring still
  calls `Agent.model` (a small follow-up to wire the named-
  provider config).

- **feat-008 — Findings & output shapes.** Ships the four
  built-in `Finding` variants and their renderers, plus a
  registry for dispatch. The `Finding` Protocol itself shipped
  earlier under feat-001.

  *New in `agentforge` (runtime):*
  - **`SimpleFinding`** — severity / category / message /
    recommendation / file / line / rule_id / metadata. The
    default variant for issue-list outputs (code review, audits,
    lints).
  - **`PatchFinding`** — wraps a structured `Patch` with
    rationale + `confidence` (validated to `[0, 1]`). For
    refactor bots, codemod agents, auto-fix suggestions.
  - **`NarrativeFinding`** — markdown `body` + `references` list.
    For docs Q&A, research summaries, explanatory output.
  - **`MultiSpanFinding`** — one logical issue across `>=1`
    `Span`s (file + line range + excerpt). For cross-file
    findings like "hard-coded secret in 3 files".
  - **`Patch`** (file + diff + hunk_count), **`Span`** (file +
    start/end line + excerpt) — helper value types two variants
    embed. `Span` enforces `end_line >= start_line` at
    construction.
  - All six are **frozen Pydantic v2 models** (deviation from
    spec §4.2's `@dataclass`; ADR-0014 supersedes — see the
    Implementation section in the spec for the rationale). Each
    has `to_dict()` (delegates to `model_dump(mode="json")`) and
    a `classmethod from_dict(d)` for typed round-trip.
  - **`RendererRegistry`** — maps `Finding` (sub)types to
    `FindingRenderer`s via isinstance-based **most-specific-wins**
    dispatch. `register(type, renderer)` (replaces in-place on
    re-registration, preserving order); `get(finding)` (raises
    `MissingRendererError` on no match); `registered_types()`
    diagnostic.
  - **`RendererRegistry.default()`** — factory pre-populated with
    the four built-in renderers. The common case for agent code.
  - Four built-in renderers, one per variant: **`ScorecardRenderer`**
    (text: severity-tagged line; markdown: GFM table row),
    **`PatchApplierRenderer`** (text: header + unified diff;
    markdown: same wrapped in a fenced ` ```diff ` block — does
    not apply the patch), **`MarkdownRenderer`** (text: prose with
    "References:" footer; markdown: heading + body + `###
    References`), **`SpanTableRenderer`** (text: per-span block;
    markdown: pipe-escaped GFM table + Recommendation footer).
  - All renderers support `"text"` and `"markdown"` formats;
    unknown formats raise `ValueError`. Each overrides
    `supports(finding_type)` so a custom variant subclassing a
    built-in routes through the same renderer.

  *New in `agentforge-core` (Tier-1 contract):*
  - **`FindingRenderer`** ABC — single abstract method
    `render(finding, format="text") -> str` plus a default
    `supports(finding_type) -> bool` (returns False; subclasses
    pin to specific variants). Adding methods to the ABC requires
    a major bump under ADR-0007.

  Top-level re-exports from `agentforge`: `SimpleFinding`,
  `PatchFinding`, `NarrativeFinding`, `MultiSpanFinding`, `Patch`,
  `Span`, `RendererRegistry`, `ScorecardRenderer`,
  `PatchApplierRenderer`, `MarkdownRenderer`, `SpanTableRenderer`,
  `MissingRendererError`. `FindingRenderer` is re-exported from
  `agentforge_core` top-level.

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

### Docs

- **Runbook sections backfilled for shipped features.** The
  runbook policy was locked mid-feat-007 (each feature PR adds a
  task-oriented `## Runbook` section to its canonical spec for
  agent developers building on AgentForge). This chore retroactively
  authors runbooks for the five already-shipped features:
  - feat-001 (Core contracts & `Agent`) — minimum agent, budget
    caps, step trace, hooks, config, sync shim, when-not-to-use.
  - feat-002 (Reasoning strategies) — picking a strategy, tuning
    ReAct / Plan-Execute / ToT (judge scorer) / MultiAgent
    Supervisor, reading per-step output, when not to use.
  - feat-003 (LLM provider abstraction — Bedrock) — basic config,
    cross-region inference profiles, prompt caching, extended
    thinking, embeddings, cost accounting, custom-provider
    registration, when not to use Bedrock.
  - feat-004 (Tools system) — attaching tools, `@tool` decorator,
    locking down `shell` / `file_read`, unit-testing with
    `FakeTool`, timeouts, step inspection, when not to use a
    default tool.
  - feat-005 (Persistence) — backend picker matrix, sqlite /
    postgres / neo4j / surrealdb setup, RAG via `Retriever`,
    `(project, agent)` namespacing, `init_schema()` opt-in,
    live integration tests, when not to use each backend.

  Also fixed a stale example in feat-007's existing runbook
  (`Agent(budget=BudgetPolicy(...))`) — the Agent constructor takes
  `budget_usd=` and `max_iterations=`, not a `budget=` kwarg. Same
  fix applied while authoring feat-001's runbook.

  **Forward-reference hygiene:** every runbook eventually mentions
  unshipped features (feat-006 evaluators, feat-011 scaffolding,
  feat-012 config, feat-018 safety, feat-020 chat agents) and
  backlog packages (anthropic / openai / ollama provider drivers,
  serper / tavily tool packs). To keep those references from rotting:
  - **AGENTS.md** gets a new workflow rule — every feature PR runs
    `git grep -nE 'feat-NNN|<backlog-pkg-names>' docs/features/*.md`
    for its own number and any backlog packages it ships, and
    rewrites every match so the runbooks reflect the now-shipped
    surface.
  - **`.claude/checklists/pre-pr.md`** gains the same line as a
    blocking checklist item.
  - The boilerplate "Audience…When feat-011/019 ship…" preamble on
    each runbook is rephrased to be tense-neutral so it doesn't
    decay even if feat-011/019 slip.

### Added

- **feat-007 — Production rails (`FallbackChain` only).** Closes
  out canonical feat-007. Cost budget (`BudgetPolicy`), run-id
  propagation (`RunContext`, `current_run`, `idempotency_key_for`),
  and structured-log run-id tagging (`RunIdFilter`) all shipped
  under feat-001 already; this PR adds the last remaining piece
  — cross-provider failover.

  *New in `agentforge-core`:*
  - **`FallbackChain`** (`agentforge_core.production.fallback`)
    wraps multiple `LLMClient`s. On `retry_on` exception, falls
    through to the next provider (after retrying the current one
    `attempts_per_provider` times). Implements `LLMClient` so any
    strategy that accepts an `LLMClient` accepts a chain
    transparently.
  - String providers resolve via the global `Resolver` (same path
    as `Agent(model="bedrock:…")`).
  - `capabilities()` returns the **intersection** of every wrapped
    provider's capabilities; a chain can only honestly claim what
    every fallback delivers.
  - Optional methods (`call_with_cache`, `call_with_thinking`)
    raise `CapabilityNotSupported` unless every wrapped provider
    declares the capability (capability-intersection rule).
  - `stream` raises `CapabilityNotSupported` unconditionally;
    streaming with cross-provider fallback semantics is harder
    than the unary call and deferred to a follow-up.
  - `last_used_provider` (int | None) tracks the index of the
    provider that answered the most recent call (diagnostic).
  - `close()` cascades in reverse-construction order; individual
    close failures are logged and swallowed (best-effort cleanup).

  *Public surface:*
  - `from agentforge import FallbackChain` (also
    `from agentforge_core import FallbackChain`).

  *Coverage:* 23 unit tests for the chain itself + 4 Agent-
  integration tests covering constructor wiring, ReActLoop
  dispatch, fallback on RateLimitError, top-level import.

  *New workflow rule (locked in 2026-05-10):* every feature PR
  now adds a **`## Runbook` section** to the matching canonical
  spec. Audience: agent developers using AgentForge to build
  production agents. Task-oriented "how do I configure / tune /
  debug" content. When feat-011 (Copier scaffolding) and feat-019
  (runbook system) ship, the templating engine consumes these
  sections into scaffolded agent projects. feat-007's spec is the
  first to carry one (configure cross-provider fallback, tune
  retries, combine with budget, read run_id from a tool, debug
  "every provider failed", etc.). Already-shipped features
  (feat-001/002/003/004/005) get backfilled in a separate
  `chore/backfill-runbooks` PR.

- **feat-004 — Tools system.** Adds the decorator + default tools +
  dispatch enhancements that turn a typed Python function into a
  ready-to-use `Tool`, and the four default tools every agent gets
  out of the box.

  *New in `agentforge`:*
  - **`@tool`** decorator (`from agentforge import tool`) — wraps a
    typed function as a `Tool` subclass with `name`, `description`,
    and `input_schema` inferred from the function signature and
    Google-style docstring. Bare form (`@tool`) and parameterised
    form (`@tool(name=..., capabilities=...)`) both supported. Sync
    and async functions both work. Decoration-time validation:
    missing type hints, variadic args, and positional-only params
    all raise `ValueError` with a clear message.
  - **`agentforge.tools`** — public namespace for default tools:
    - `calculator` — arithmetic via Python's `ast` module (no
      `eval()`); supports `+ - * / // % **` and parens.
    - `file_read` / `FileReadTool` — sandboxed UTF-8 file read with
      a configurable working dir and size cap (default 1 MiB).
      Capabilities: `{"filesystem"}`.
    - `shell` / `ShellTool` — sandboxed subprocess via
      `asyncio.create_subprocess_exec` (`shell=False` semantics; no
      shell-injection vector). Default 30s timeout, 64 KiB output
      cap, optional `allowed_commands` whitelist. Capabilities:
      `{"shell", "destructive"}`.
    - `web_search` / `WebSearchTool` / `SearchResult` — pluggable
      search backend with a DuckDuckGo HTML scrape default. Real
      backends (Serper, Tavily, Brave) ship as separate module
      packages later. Capabilities: `{"network"}`.

  *Strategy improvements:*
  - **`_StrategyBase._dispatch_tool`** centralises the tool-call
    boundary per spec §4.3:
    1. Tool not registered → `Error: tool 'x' is not registered…`
       observation (no exception).
    2. Validation failure on
       `input_schema.model_validate(arguments)` → `Error: invalid
       arguments…` observation. The LLM sees the Pydantic error
       message and self-corrects on the next iteration.
    3. `await tool.run(**validated)` wrapped in
       `asyncio.wait_for(timeout=timeout_s)`. Default 30 s
       (`agentforge.strategies._base.DEFAULT_TOOL_TIMEOUT_S`); pass
       `timeout_s=None` to disable.
    4. Any exception from the tool body → `Error: {ExcClass}: {msg}`
       observation. Tools should raise rather than catch — the
       strategy turns the raise into the LLM's observation.
  - `ReActLoop` and `PlanExecuteLoop` now use the helper
    consistently. `PlanExecuteLoop` preserves its replan-on-failure
    semantics by re-raising "Error:" observations so the existing
    `_StepFailure` machinery can decide whether to replan.

  *Test isolation:*
  - **`agentforge._testing.FakeTool.fake(name, response_or_fn)`** —
    minimal scripted-response Tool. Static values, sync callables,
    and async callables all supported. Records every `run` call's
    kwargs in `self.calls` for assertions. `isinstance(fake, Tool)`
    holds, so `Agent(tools=[fake, …])` accepts them without
    special-casing.

  *Coverage:* 75 new unit tests (decorator, default tools,
  dispatch helper, FakeTool) plus a live integration test for the
  DuckDuckGo backend gated on `RUN_LIVE_WEB=1`.

  *Capability vocabulary now in use:* `{"filesystem", "network",
  "shell", "destructive"}` — declared per default tool. Future
  safety guardrails (feat-018) will consume this vocabulary to
  gate destructive tool use behind explicit operator opt-in.

  *Pre-commit housekeeping:* migrated the ruff hook id from the
  legacy alias `id: ruff` to the modern `id: ruff-check`. No
  behavioural change; the previous "(legacy alias)" log line is
  gone.

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
