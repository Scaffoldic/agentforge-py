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
