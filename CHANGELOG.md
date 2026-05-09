# Changelog

All notable changes to `agentforge-py` are documented here. The format
is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The framework follows a coordinated release train (per ADR-0015): every
release tag bumps every workspace member to the same minor version.

## [Unreleased]

### Changed

- Documentation made self-contained for the public OSS repo: removed
  `../../` references to a private design workspace from `AGENTS.md`,
  `README.md`, the PR template, and the pre-commit config. Repo
  conventions, install instructions, and the contributor workflow now
  live entirely inside `agentforge-py`.

### Added

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
