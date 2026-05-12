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

- **feat-020 — Chat agents (Python v0.2 scope).** Three new
  workspace members + locked contracts in core. Wraps the
  one-shot `Agent` into a multi-turn, stateful conversation
  with multi-tenant isolation, per-turn / per-session budgets,
  per-turn input/output guardrails, idempotency, and a FastAPI
  HTTP + WS + SSE server.

  *Contracts (`agentforge-core`):*
  - `agentforge_core.contracts.chat.{ChatHistoryStore,
    HistoryTruncationStrategy}` ABCs.
  - `agentforge_core.values.chat.{ChatTurn, SessionInfo,
    ChatChunk, ChatResponse}` frozen Pydantic value models.
  - `run_chat_history_conformance(store)` +
    `run_truncation_conformance(strategy)` harnesses.

  *Chat runtime (`agentforge-chat`):*
  - `ChatSession(agent, *, session_id, history_store,
    system_prompt, truncation, owner, per_turn_budget_usd,
    per_session_budget_usd, idempotency_window_s, on_turn)`.
  - `send(message, *, idempotency_key, cancellation)` and
    `stream(...)` (buffer-then-stream; sentence-segmented text
    chunks + done/error sentinels).
  - `history(...)`, `reset()`, `close()`.
  - `InMemoryChatHistory` (asyncio-lock protected, in-memory
    TTL sweep) + `SqliteChatHistory` (aiosqlite-backed, mirrors
    `SqliteMemoryStore`).
  - Four truncation strategies: `SlidingWindow`, `TokenBudget`,
    `SummariseOldest`, `Hybrid`. Pair-atomicity invariant
    enforced.
  - Per-session `asyncio.Lock` registry +
    `IdempotencyCache` LRU+TTL.
  - Entry-points under `agentforge.chat.history` /
    `agentforge.chat.truncation`; `manifest.yaml` for
    `agentforge add module chat`.

  *HTTP server (`agentforge-chat-http`):*
  - `ChatServer(agent_factory, history_store, auth, host, port,
    cors_origins, rate_limit_per_session_per_minute,
    truncation)` — FastAPI app with REST + WebSocket + SSE.
  - `BearerAuthPolicy` ABC + `EnvBearerAuth(token_env_var)`
    placeholder (refactors to feat-014's `AuthPolicy` when
    shipped).
  - Multi-tenant: cross-owner access returns 403; missing /
    invalid bearer returns 401; rate-limit overflow returns
    429.
  - WebSocket cancellation: disconnect aborts the in-flight
    consume coroutine.

  *Config + wiring:*
  - `modules.chat:` config block (`ChatHistoryDriverConfig`,
    `ChatTruncationConfig`, `ChatSessionConfig`, `ChatConfig`).
  - `validate_module_configs` extension via new
    `_validate_driver` helper.
  - `agentforge_chat.build_chat_session_from_config(config,
    agent)` resolves drivers via the global resolver.
  - `agentforge.register_chat_history` /
    `register_chat_truncation` resolver helpers.

  *v0.3 follow-ups (deferred):*
  - `agentforge-chat-history-postgres`,
    `agentforge-chat-history-redis`,
    `agentforge-chat-slack` reference adapter.
  - Real per-token streaming through the strategy loop.
  - Cross-process per-session locking (Redis-backed).
  - Provider-aware tokenisation in `TokenBudget`.

  Shipped via PR #26. See spec
  `docs/features/feat-020-chat-agents.md` §11–§12.

- **feat-015 — Pipeline & deterministic tasks (full spec).** New
  framework-level subsystem inside `agentforge` for deterministic,
  pre-LLM analysis steps. Findings flow back into the LLM loop two
  ways: as a per-run system-prompt addendum and via a built-in
  `pipeline_findings` tool.

  *Contracts (`agentforge_core`):*
  - `agentforge_core.contracts.task.Task` ABC — `name`,
    `cost_estimate_usd`, `timeout_s`, `depends_on` ClassVars;
    `async run(context) -> list[Finding]`.
  - `agentforge_core.values.pipeline.PipelineResult` frozen
    Pydantic value with `findings`, `task_durations_ms`,
    `task_failures`, `total_cost_usd`.
  - `FinishReason` literal extended with `"pipeline"`.
  - `run_task_conformance(task)` harness in
    `agentforge_core.testing`.

  *Engine (`agentforge.pipeline`):*
  - `Pipeline(tasks, *, max_concurrent, on_task_error)` —
    constructs once (DAG validation: duplicates / missing deps /
    cycles), runs once per agent invocation. `asyncio.Semaphore`
    caps in-flight tasks; `asyncio.wait_for(timeout_s)` per task.
  - `on_task_error="continue"` (default) emits a
    `SimpleFinding(category="pipeline.task_failure", rule_id=
    <task_name>)` on failure; dependents still run. `"fail"`
    raises `PipelineFailure` after cancelling outstanding
    runners.
  - `PipelineFindingsTool` built-in tool — `name="pipeline_findings"`,
    filters by `category` / `severity`, returns JSON-friendly
    dicts.
  - `register_task(name)` resolver helper.

  *Agent integration (`agentforge.agent`):*
  - `Agent(pipeline=Pipeline(...))` kwarg.
  - `Agent.run(task, *, context=None, replay_pipeline=None)` —
    runs the pipeline before the strategy loop; appends a
    markdown addendum to the per-run system prompt (the
    configured prompt is not mutated); commits pipeline cost
    against the run budget (over-budget raises `BudgetExceeded`
    pre-LLM).
  - `PipelineFailure` propagates with `finish_reason =
    "pipeline"`.

  *Config + CLI (`agentforge_core.config`, `agentforge.cli`):*
  - `modules.pipeline:` block with `enabled`, `max_concurrent`,
    `on_task_error`, `tasks: [{name, config}]`.
  - `validate_module_configs` walks each task entry against its
    `config_schema` (if declared).
  - `build_pipeline_from_config(cfg)` wired into
    `build_agent_from_config`.
  - `agentforge run --replay <id>` reads the recorded
    `__pipeline` claim and threads it via
    `Agent.run(replay_pipeline=...)` so side-effect-bearing
    tasks don't double-run.

  *Recording + replay (`agentforge.recording`, `agentforge.replay`):*
  - `PIPELINE_CATEGORY = "__pipeline"` reserved claim category +
    `record_pipeline_result(...)` helper.
  - `load_pipeline_result(memory, run_id) -> PipelineResult |
    None`.

  *Public re-exports (`agentforge`):*
  - `Pipeline`, `Task`, `PipelineResult`, `PipelineFailure`,
    `PipelineFindingsTool`, `register_task`.
  - `agentforge.testing.run_task_conformance`.

  Shipped via PR #25. See spec
  `docs/features/feat-015-pipeline-and-tasks.md` §10–§11.

- **feat-013 — MCP integration (full spec).** New Tier-3 sister
  package `agentforge-mcp`. Two halves: consume upstream MCP
  tool servers (stdio + HTTP + SSE) and (optionally) expose
  this agent's tools as an MCP server.

  *Foundations in `agentforge_mcp._runner`:*
  - `MCPClientRunner` Protocol (slice of `mcp.ClientSession`):
    `list_tools`, `call_tool`, `close`.
  - `MCPServerRunner` Protocol (slice of `mcp.server.Server`):
    `register_tool`, `serve`, `stop`.
  - `MCPToolDescriptor` frozen dataclass (name + description +
    JSON-Schema dict).

  *Consumer (`agentforge_mcp.client`):*
  - `MCPServerClient(name, runner, tool_filter)` is the bare
    constructor (tests).
  - `from_stdio` / `from_http` / `from_sse` factories lazy-
    import the upstream `mcp` SDK; missing-SDK surfaces
    `ModuleError` with pip remediation.
  - `discover_tools()` returns `MCPToolAdapter` instances —
    each is a synthesised `Tool` subclass whose name is
    prefixed with the server name (`fs.read_file` /
    `s3.read_file` — no collisions across servers) and whose
    `input_schema` is a permissive Pydantic v2 model built
    from the MCP descriptor.
  - `tool_filter` restricts the imported subset; empty = all.

  *Exposer (`agentforge_mcp.server`):*
  - `MCPServer(tools, runner, allowed)` plus
    `from_stdio` / `from_http` factories. `register_tools()`
    publishes each whitelisted tool with its description +
    `model_json_schema()`; an allowlist of `None`/`()` exposes
    everything, a non-empty tuple is strict-allowlist.
  - Each registered handler closes over the local `Tool` so
    inbound MCP requests round-trip back through
    `tool.run(**args)`.

  *Orchestrator (`agentforge_mcp.bridge`):*
  - `MCPBridge(clients, server)` ties the two halves together.
  - `from_config(config)` parses the `modules.protocols.mcp`
    block; `start()` opens every client + discovers tools +
    schedules the optional server's `serve()` as an asyncio
    task; `close()` cancels the task cleanly + closes every
    client.
  - Tools land in `bridge.tools` ready to pass to
    `Agent(tools=...)`.

  *Manifest:* `manifest.yaml` ships so `agentforge add module
  mcp` registers the protocol entry under
  `modules.protocols`.

  *Workspace + CI:* new `packages/agentforge-mcp/` member; root
  `pyproject.toml`, `.pre-commit-config.yaml`, and CI args
  extended. mypy override added for `mcp.*` (the SDK ships
  without `py.typed`).

  Production transport runners (`_SDKClientRunner` /
  `_SDKServerRunner`) are scaffolded but scoped to
  `# pragma: no cover` and raise `ModuleError("Production MCP
  runner not implemented yet")` — the framework's first live
  integration test will wire them; the contract surface is
  complete via the runner protocols and the
  fake-runner-driven unit tests.

  Tests: 21 unit cases across `test_adapter`, `test_client`,
  `test_server`, `test_bridge` — schema synthesis, name
  prefixing, tool-filter subsets, lazy-import error paths,
  allowlist semantics, handler round-trips, bridge tool
  aggregation, lifecycle cancellation.

  *Spec*:
  `docs/features/feat-013-mcp-integration.md` — Implementation
  Status §10 + Runbook §11.

- **feat-019 — Developer experience + AI rules.** Every
  `agentforge new` scaffold now ships with 16 task-oriented
  runbooks plus AI-assistant rules (`AGENTS.md`, `CLAUDE.md`,
  `.cursorrules`) framework-managed and upgrade-safe.

  *Three-section managed/custom file format.* New helpers in
  `agentforge.cli._scaffold_state`:
  - `split_three_section(content) -> (managed, custom)` and
    `merge_three_section(new_managed, existing_custom)` use the
    `<!-- agentforge:end-managed -->` / `<!-- agentforge:custom
    -->` / `<!-- agentforge:end-custom -->` markers (valid HTML
    comments so common markdown linters don't choke).
  - `agentforge upgrade` rewrites the managed section while
    preserving the developer-owned custom tail.

  *Shared scaffold injection.* New
  `agentforge.cli._shared_scaffold.inject_shared_scaffold(dst,
  template_name, template_version)`:
  - Walks `agentforge.templates._shared` via
    `importlib.resources`.
  - `.tmpl` files render through Jinja (`autoescape=False` —
    markdown output, never HTML rendered to a browser); the
    suffix is stripped on write.
  - Non-`.tmpl` files copy verbatim apart from a marker header.
  - Lock entries are written under
    `source_module: "template:<name>:_shared"` so the shared
    files participate in `agentforge upgrade` / `fork`.
  - `agentforge new` calls the injection automatically after
    Copier finishes.

  *Content shipped under `agentforge/templates/_shared/`:*
  - `AGENTS.md.tmpl` — ~115-line canonical AI-rules document.
    Project shape, file ownership (AGENTFORGE-MANAGED /
    -FORKED markers + three-section format), architecture
    invariants (tools / strategy / LLM clients / memory /
    budget / run_id / guardrails), a runbook reference table,
    anti-pattern list (LangChain idioms, hand-rolled JSON
    schemas, raw SQL, cost-bypass, defensive try/except), pre-
    commit checks.
  - `CLAUDE.md` — thin pointer with a managed message + custom
    section.
  - `.cursorrules` — same pattern for Cursor.
  - `docs/runbooks/README.md.tmpl` + 16 runbooks (01-set-up,
    02-add-a-tool, 03-add-a-pipeline-task, 04-pick-strategy,
    05-write-prompts, 06-test, 07-debug, 08-add-memory, 09-add-
    mcp, 10-add-evaluators, 11-add-safety, 12-add-observability,
    13-multi-provider, 14-deploy, 15-upgrade, 16-config). Each
    follows the locked contract (Goal/Time/Prereqs/TL;DR/Step-
    by-step/Variations/Symptom→Cause→Fix table/Related).

  *New CLI subcommand `agentforge docs`:*
  - `docs` lists every numbered runbook in `docs/runbooks/`.
  - `docs <topic>` opens by filename stem, `.md` filename,
    bare number, or alias (substring match against the
    stripped stem). Uses `$EDITOR`; falls back to stdout.
  - `docs --check` hashes every local runbook (marker line
    stripped) against the framework's bundled copy; reports
    `+local` / `~drift` and exits 1 when drift is present.
  - `docs --serve` starts a SimpleHTTPRequestHandler on port
    8765 over the runbooks directory.

  Tests: 5 unit cases for three-section format; 5 for shared
  scaffold injection; 10 for `agentforge docs`. Full pre-commit
  gate green (ruff + mypy --strict + bandit + pytest + coverage
  ≥ 90%).

  *Spec*:
  `docs/features/feat-019-developer-experience-and-ai-rules.md`
  — Implementation status §10 + Runbook §11.

- **feat-018 — Safety & security guardrails (full surface).**
  Adds the framework's input / output / tool-gate validation
  pipeline plus four vendor sister packages.

  *New ABCs in `agentforge-core`:*
  - `InputValidator.validate(content, context) -> ValidationResult`
  - `OutputValidator.validate(content, context) -> ValidationResult`
    (with optional `redacted_content`)
  - `ToolCallGate.authorize(tool_name, tool, args, context) ->
    ValidationResult`
  - `ValidationResult` frozen Pydantic value (passed, score in
    [0,1], violations tuple, redacted_content, metadata) +
    `.ok()` factory
  - `GuardrailPolicy` (Pydantic config model, lives in
    `agentforge_core.config.schema` to avoid an import cycle
    through `values/state.py`): conservative defaults — block on
    input violations, redact on output, block on tool gate
    denial, fail-closed on validator exceptions
  - `ModulesConfig.guardrails: GuardrailsConfig` field +
    `GuardrailEntry` shape for declarative config

  *New built-ins in `agentforge.guardrails`:*
  - `PromptInjectionBasic` — regex pack catching the obvious
    "ignore previous instructions" / DAN / jailbreak / system-
    prompt-leak phrasings.
  - `PIIRedactBasic` — regex detector for email / phone / SSN /
    credit-card / IPv4; emits `<redacted:KIND>` placeholders in
    `redacted_content`.
  - `CapabilityCheck` — denies tools tagged `destructive` unless
    explicitly allowlisted via `destructive_allow`.
  - `Allowlist` — bare-name allowlist for tool dispatch.

  Each registers with the global Resolver under
  `guardrails.{input,output,tool_gates}` at import time so
  external configs reference them by name.

  *Agent integration:*
  - `GuardrailEngine` (`agentforge/guardrails/engine.py`) runs
    every validator in series, wraps the LLM client +
    every tool with guardrail-aware proxies, emits one
    `agentforge.audit` log record per decision, and isolates
    validator exceptions (block under `fail_open=False`).
  - `Agent.__init__` accepts `input_validators`,
    `output_validators`, `tool_gates`, `guardrail_policy` kwargs.
  - `Agent.run` enforces input validation at the start, wraps
    LLM + tools transparently for the strategy loop, and
    surfaces every decision on `RunResult.guardrail_events`.
  - Configuration: top-level `guardrail_policy` plus
    `modules.guardrails.{defaults,input,output,tool_gates}`
    (autoinstall of built-in defaults via `defaults: true` is
    a follow-up, currently a no-op marker).

  *Conformance harnesses* re-exported from `agentforge.testing`:
  `run_input_validator_conformance`,
  `run_output_validator_conformance`,
  `run_tool_gate_conformance`. Each asserts the locked-contract
  invariants on a passed-in validator instance.

  *Four new Tier-3 sister packages*:
  - `agentforge-guard-llmguard` — `LLMGuardInput` adapter for
    LLM Guard's scanner suite (jailbreak / prompt_injection /
    ban_substrings / secrets). Inverts LLM Guard's risk score
    into the framework's "1 = clean" semantics.
  - `agentforge-guard-presidio` — `PresidioOutput` adapter with
    `entities` / `score_threshold` / `action: redact|score-only`.
    Returns `<ENTITY_TYPE>` placeholders in `redacted_content`.
  - `agentforge-guard-nemo` — `NemoInput` + `NemoOutput` adapters
    for NeMo Guardrails Colang rails. Constructor accepts either
    a `config_path` directory or an injected `NemoRunner`.
  - `agentforge-guard-llamaguard` — `LlamaGuardInput` +
    `LlamaGuardOutput` for Meta Llama Guard 3. Parses
    `safe` / `unsafe S1..S14` replies; carries raw response into
    `metadata`.

  Each vendor module:
  - Registers via pyproject `[project.entry-points."agentforge.
    guardrails.{input,output}"]`.
  - Wraps a `Runner` protocol so unit tests inject a fake without
    requiring the upstream SDK installed.
  - Lazy-imports the upstream package; surfaces `ModuleError`
    with pip remediation if missing.

  *Workspace + CI*:
  - Four new workspace members under `packages/agentforge-guard-*/`.
  - Root `pyproject.toml`: workspace deps, sources, coverage,
    testpaths.
  - mypy overrides for `llm_guard.*`, `presidio_analyzer.*`,
    `presidio_anonymizer.*`, `nemoguardrails.*` (all four ship
    without `py.typed` or aren't installed by default).
  - `.pre-commit-config.yaml` + `.github/workflows/ci.yml`:
    mypy, bandit, pytest-unit args extended with each new src +
    tests path.

  *Spec*: `docs/features/feat-018-safety-and-security-guardrails.md`
  — Implementation status §10 + Runbook §11.

- **feat-016 — Testing framework (full surface).** Public test
  helpers in the `agentforge` runtime package plus a new sister
  package for richer use cases.

  *New public namespace `agentforge.testing` in `agentforge`:*
  - `MockLLMClient` (`llm.py`) implementing `LLMClient`.
    Factories: `from_script([{text, tool_calls, stop_reason,
    usage, ...}])`, `deterministic(response)`,
    `from_recording(path)`. Tracks `call_count` and
    `tool_calls_observed` so tests can assert on what the agent
    asked the LLM to call without manually inspecting each
    response. Exhausted calls raise `ModuleError`.
  - `FakeTool` and `FakeLLMClient` are re-exported from the
    private `_testing` namespace; new code uses the public path,
    the private one stays as a back-compat shim for the
    framework's own pre-feat-016 internal tests.
  - `agent_factory(model, tools, strategy, **overrides)` —
    constructs an Agent with safe test defaults
    (`MockLLMClient.deterministic("ok")`, no tools, single-step
    LLM-call strategy, in-memory store, budget 0.10 USD, max
    iterations 3, no log-filter mutation). All defaults
    overridable.
  - `agentforge.testing.fixtures.mock_llm` and
    `temp_memory_store` — pytest fixtures.
  - `agentforge.testing.conformance` re-exports
    `run_memory_conformance`, `run_strategy_conformance`,
    `run_vector_conformance` from `agentforge-core` so external
    driver authors have one canonical import path.
  - `record_llm(real, path, *, redactions=None)` wraps a real
    `LLMClient` and writes a JSONL cassette (`{request_hash,
    request, response}` per call, with a versioned header line).
    Default redactions cover `api_key` / `authorization` /
    `bearer` recursively. `load_recording(path)` returns
    `(header, entries)` for inspection.

  *New Tier-3 package `agentforge-testing`:*
  - `GoldenSetRunner.from_jsonl(path).run(agent_factory)` — load
    JSONL fixtures, drive an agent through each, compare outputs
    via exact / `contains` / `regex` / `any_of` matchers.
    `mode="fail-fast"` raises `GoldenMismatch` (an
    `AssertionError` subclass) on the first mismatch.
  - `assert_snapshot(actual, path)` — Approval-style file
    snapshot. Creates the file on first run; subsequent runs
    compare byte-for-byte. `UPDATE_SNAPSHOTS=1` in the
    environment re-records.
  - `analyze_recording(path) -> RecordingStats` — aggregate
    stats (call_count, tokens_in/out, cost_usd, tool-call
    histogram, redactions, format_version).

  *Workspace + CI*:
  - New workspace member `packages/agentforge-testing/`.
  - Root `pyproject.toml`, `.pre-commit-config.yaml`, and
    `.github/workflows/ci.yml` extended with the new src + tests
    paths.

  *Spec*: `docs/features/feat-016-testing-framework.md` —
  Implementation status §10 + Runbook §11.

- **feat-017 — CLI runtime (full operator surface).** Ships the
  v0.1 / v0.2 operator commands plus the persistence + replay
  foundations they need.

  *New CLI subcommands in `agentforge`:*
  - **`agentforge run`** — positional task xor `--task-file`,
    `--override key=value` (repeatable, dotted-path),
    `--output-format {rich,json,plain}` (default rich on TTY else
    plain; Rich is soft-imported), `--replay RUN_ID --to-step N`
    (replays via `ReplayLLMClient`), `--record` (installs the
    recording hook). Exit codes locked at 0/1/2/3/4 (success,
    generic, config-invalid, budget-exceeded, guardrail-tripped).
  - **`agentforge eval --fixtures JSONL --threshold T`** —
    iterates fixtures (`{task, expected, metadata}`), applies the
    config's evaluators, aggregates a mean score, exits 5 on
    threshold failure. Output formats: rich, json, junit (JUnit
    XML via stdlib `xml.etree`, output-only).
  - **`agentforge debug --replay RUN_ID`** — interactive stdlib
    `cmd.Cmd` REPL with `step` / `back` / `state` / `inspect
    FIELD` / `steps` / `quit`. Plain text only, no Rich
    dependency.
  - **`agentforge db {migrate,backup,restore,purge,query}`** —
    routes to the configured `MemoryStore`. `migrate` calls
    `init_schema()` when present (no-op + exit 0 otherwise).
    `backup` / `restore` round-trip every claim as JSON Lines.
    `purge --older-than DUR|--run-id|--category` confirms unless
    `--yes`. `query` parses a tiny `key:value` DSL with keys
    `category|agent|project|run_id`.
  - **`agentforge health`** — preflight: config loads + validates,
    every module returned by `Resolver.list_installed()` is
    resolvable, every declared backend is reachable. Output
    formats: plain, json. Renamed from the spec's `agentforge
    status` to avoid collision with feat-011's scaffolding-state
    `status` command — recorded as a deviation in the feat-017
    spec.

  *New foundations:*
  - **`MemoryStore.delete(*, run_id=None, older_than=None,
    category=None) -> int`** added to the ABC. Conjunctive
    filters, refuses to wipe when every filter is None, returns
    affected-row count. Implemented on the in-memory default and
    every shipped driver (sqlite, postgres, neo4j, surrealdb).
    Conformance suite gains a `_run_delete_conformance` sub-suite
    (no-filter-refuses, delete-by-run-id, delete-by-category).
    Postgres runner gains
    `execute_returning_count(sql, *params)` parsing the asyncpg
    `DELETE N` status tag.
  - **Run-recording protocol** (`agentforge.recording`).
    `RecordRunHook(memory, project, agent_name)` persists every
    emitted `Step` under `category="__step"`, every `EvalResult`
    under `category="__eval"`, and a final summary claim under
    `category="__run"`. Reserved category names are part of the
    v0.1 on-disk contract.
  - **Replay primitives** (`agentforge.replay`).
    `ReplayLLMClient.from_recording(memory, run_id)` implements
    `LLMClient` by replaying recorded LLM responses in order.
    `replay_tools(memory, run_id, tools)` wraps each tool so
    `run()` returns recorded observations. `ReplayExhausted`
    surfaces overshoots clearly.
  - **`Agent(record_runs=memory)`** — opt-in hook wiring so the
    agent persists its own trace when configured.
  - **`build_agent_from_config(config)`** in
    `agentforge.cli._build` — central wiring helper resolving
    providers / memory / evaluators / strategy / tools from
    `agentforge.yaml` via the global `Resolver`. Forwards
    strategy / system_prompt / budget / max_iterations into
    `Agent()` so the wired agent honours the YAML without
    needing `config_path`.

  *Other notes:*
  - argparse-based (no Typer dep added) — matches feat-010/011/012.
  - Templates ship in-wheel (inherited from feat-011).
  - `pyproject.toml`: `filterwarnings` demotes `ResourceWarning`
    and `PytestUnraisableExceptionWarning` from error → warning.
    Multiple `asyncio.run` callsites in the test suite on macOS
    occasionally surface a stale kqueue selector reference during
    interpreter shutdown; the loops have actually been closed.

  *Spec*:
  `docs/features/feat-017-cli-runtime.md` — Implementation status
  §10 + Runbook §11 + exit-codes contract.

- **feat-011 — Scaffolding & upgrade.** Ships the `agentforge new`
  scaffolder, six starter templates, three-way-merge `agentforge
  upgrade`, and the `fork` / `unfork` / `status` file-ownership
  workflow. Day-1 → Day-365 story now resolved in Python.

  *Templates (ship inside the `agentforge` wheel, rendered via
  Copier with `_templates_suffix: ""` so file contents render
  Cookiecutter-style):*
  - `minimal` — one Agent, one tool, no persistence.
  - `code-reviewer` — `SimpleFinding` scorecard renderer wired up.
  - `patch-bot` — `PatchFinding` + `file_read` tool.
  - `docs-qa` — RAG starter (placeholder for `VectorStore`).
  - `triage` — `MultiSpanFinding` + classification rails.
  - `research` — long-horizon agent with `web_search` placeholder.

  Each template ships `copier.yml`, `agentforge.yaml`,
  `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, and
  `src/{{project_slug}}/{__init__.py,main.py}`.

  *New CLI subcommands in `agentforge`:*
  - **`agentforge new <name> [--template ...]`** — runs Copier
    against the in-wheel template (resolved via
    `importlib.resources.files("agentforge.templates")`), writes
    `.agentforge-state/managed-files.lock`, and prepends
    `AGENTFORGE-MANAGED: <template>@<version> hash:<sha256-prefix>`
    headers to every managed file. Comment style is per-extension
    (`#` for py/yaml/sql, `//` for js/ts, `<!-- -->` for html/md).
  - **`agentforge upgrade [--to <ref>] [--dry-run]`** — wraps
    Copier's `run_update` for the three-way merge against the
    template version recorded in `.agentforge-state/answers.yml`.
    Refreshes the managed-files lock afterwards, preserving any
    entries flagged `forked`.
  - **`agentforge fork <path>`** — strips the marker header, sets
    `forked=true` in the lock. Future upgrades skip the file.
  - **`agentforge unfork <path>`** — clears the flag and
    re-prepends the marker; the next `agentforge upgrade` pulls
    template content.
  - **`agentforge status`** — walks the lock and prints files
    grouped by `MANAGED` / `FORKED` / `DRIFTED` / `MISSING`. Drift
    detection strips the marker line before hashing so prepending
    a marker doesn't make a managed file look drifted.

  *New module:* `agentforge.cli._scaffold_state` — pure functions
  for lock I/O, `marker_for`, `hash_content`, `strip_marker`,
  `write_managed_files_lock`, `prepend_markers`, `file_status`.

  *Dependencies:* added `copier>=9.4` to `agentforge`.

  *Tooling:* templates contain Jinja-embedded `.py` / `.toml`
  files and `{{project_slug.replace('-', '_')}}` directories that
  aren't valid Python packages. Added
  `packages/agentforge/src/agentforge/templates/` to the mypy
  `exclude`, ruff `extend-exclude`, and global pre-commit
  `exclude` patterns. The templates dir is shipped via
  `[tool.hatch.build.targets.wheel.force-include]` so hatchling
  preserves the `{{project_slug}}/...` path inside the wheel.

  *Tests:* 12 unit tests cover `agentforge new` plus a
  parametrised smoke test that renders every shipped template; 23
  unit tests cover `_scaffold_state` (marker styles, lock capture,
  idempotency, all four `file_status` states, fork/unfork
  roundtrip, upgrade dry-run).

  *Deviations from the spec.* Templates ship in-wheel (not a
  separate `agentforge-templates` repo) — keeps v0.x installs
  network-free. `unfork` is partially restorative: it re-prepends
  the marker but defers content re-render to the next `upgrade`.
  `--run-tests` on upgrade is deferred. The TypeScript engine
  (ADR-0021) and CI upgrade matrix are out of scope for this PR.

  *Spec*:
  `docs/features/feat-011-scaffolding-and-upgrade.md` — Implementation
  status §10 + Runbook §11.

- **feat-010 destructive CLI (sub-feat completion).** Ships the
  `add` / `remove` / `swap` module commands deferred from PR #16,
  now that feat-012 (Configuration system) has landed the
  manifest-validation primitives. Completes feat-010's full
  surface.

  *New in `agentforge-core`:*
  - **Manifest value types** (`agentforge_core/values/manifest.py`):
    - `Manifest` — what a module ships at `<package>/manifest.yaml`:
      `category`, `name`, `env_vars`, `templates`, `config_block`,
      `next_steps`.
    - `EnvVarEntry` — name + description + required + optional default.
    - `TemplateFile` — package-relative source + repo destination
      + `overwrite` flag.
    - `AppliedManifest` — state record at
      `.agentforge-state/manifests/<dist>.yaml` so `remove` can
      reverse the application precisely. Tracks which env vars
      were appended, which templates were created, and whether
      the config block landed.
  - Re-exported from `agentforge_core` top-level.

  *New in `agentforge`:*
  - **`agentforge.cli.manifest_apply`** — pure-data applier:
    - `apply_manifest(...)` — idempotent: env vars append to
      `.env.example` (skip if `NAME=` present), templates copy
      from `package_root` / `importlib.resources` to destinations
      with a comment marker (`# AGENTFORGE-MANAGED: <dist>` for
      sh/py/yaml/sql; `// ` for js/ts; `<!-- -->` for html/md),
      config block deep-merges into `agentforge.yaml`. State
      written inside `try/finally` so partial failures are
      recoverable.
    - `reverse_manifest(...)` — un-append env vars, unlink
      templates, deep-strip the config block, delete state.
      Safe when artifacts are already gone.
    - `read_applied(...)` — load state or return `None`.
  - **`agentforge.cli.module_cmd`** — three CLI subcommands:
    - **`agentforge add module <distribution>`** — pip install +
      manifest discovery via `importlib.resources` + apply + state
      write + `next_steps` print. Idempotent: "already applied"
      on re-run.
    - **`agentforge remove module <distribution>`** — reverse
      applier + `pip uninstall -y`. Tolerates the package being
      already uninstalled (skips the config-block reverse).
    - **`agentforge swap <category> <from> <to>`** — composed
      remove + add. NOT transactional; documented.
  - Pip subprocess is injected via a `PipRunner` callable so
    tests don't hit the network; production calls
    `python -m pip` in the active venv.

  *Knock-on docs:* feat-010 spec's Implementation status updated —
  `add`/`swap`/`remove` move out of "What's not yet implemented"
  into the chunk table; `docs/roadmap.md`'s "destructive-CLI
  sub-feat (deferred)" section removed; `docs/features/README.md`
  catalogue row updated to reflect full feat-010 surface.

- **feat-012 — Configuration system.** Widens the minimal
  schema feat-001 shipped into the full `agentforge.yaml` surface
  (target version 0.1, foundational), plus layered env files,
  dotted-path overrides, env shortcuts, module-side schema
  integration, and the `agentforge config` CLI commands.

  *New in `agentforge-core` (schema + loader moved here from
  `agentforge`):*
  - **Widened root schema**: `AgentForgeConfig` now exposes
    `agent` (with nested `BudgetConfig`, `system_prompt_file:
    Path`, `tools`, `llm_options`), `modules` (`ModulesConfig`
    with `memory` / `graph` / `retriever` / `evaluators` /
    `observability` / `tools` / `protocols` sub-fields),
    `providers` (named-registry dict of `ProviderConfig`),
    `logging`, and `output` (`OutputConfig`).
  - **`BudgetConfig`** (nested `usd` / `max_tokens` /
    `error_streak_limit`) replaces the flat `agent.budget_usd:
    float` — breaking YAML change. The schema rejects the old
    field via `extra="forbid"`; `Agent(budget_usd=, max_iterations=)`
    kwargs remain unchanged (locked under feat-001).
  - **`agent.system_prompt_file: Path`** with string→Path coercer
    for YAML strings.
  - **Loader features**:
    - Layered env files (`agentforge.<env>.yaml` overlay via
      `AGENTFORGE_ENV` or explicit `env=` kwarg) — dict deep-merge,
      list-replace.
    - Dotted-path overrides — `parse_overrides([
      "agent.budget.usd=10", ...])`; values YAML-parsed for native
      types.
    - `AGENTFORGE_CONFIG` env var to point at a custom config
      file path.
    - `AGENTFORGE_LOG_LEVEL` env var applied post-validation to
      `cfg.logging.level`.
  - **`validate_module_configs(cfg, resolver=None, strict=True)`**
    walks `modules.*` blocks, looks each entry's class up in the
    resolver, reads `cls.config_schema: ClassVar[type[BaseModel]
    | None]`, and validates the `config:` dict against it.
    Modules without a `config_schema` accept any dict (backwards
    compatible with every shipped module).

  *New in `agentforge` (CLI):*
  - **`agentforge config validate [--path P] [--env E]
    [--override K=V] [--strict-modules]`** — schema + module-
    schema validation. Lenient by default; `--strict-modules`
    fails when referenced modules aren't installed.
  - **`agentforge config show [--path P] [--env E]
    [--override K=V] [--resolved | --raw]`** — prints the loaded
    config as YAML.
  - **`agentforge config schema [--indent N]`** — emits the root
    `AgentForgeConfig.model_json_schema()` for editor /
    SchemaStore autocomplete.

  *Knock-on docs:* `feat-001`, `feat-003`, `feat-004`, `feat-006`
  forward-tense references to "feat-012 will ship..." rewritten to
  acknowledge feat-012 has shipped the data side; the
  Agent-level auto-wiring of `modules.*` blocks is now a small
  follow-up tracked under each feature's "what's not yet
  implemented" list (and the feat-010-deferred destructive CLI).

- **feat-010 — Module discovery & resolution (runtime + read-only CLI).**
  The resolver shipped under feat-001 with an in-process registry
  only. This feature wires it to Python entry points so `pip install
  agentforge-X` makes a module discoverable without an explicit
  import, plus ships the first `agentforge` CLI command. Destructive
  commands (`add` / `swap` / `remove`) depend on feat-012
  (Configuration system) for manifest application + config-schema
  validation and are deferred to a follow-up sub-feat.

  *New in `agentforge-core`:*
  - **`ModuleInfo`** frozen Pydantic value type
    (`agentforge_core.values.module`) — `category`, `name`,
    `package` (distribution name), `version`, `cls_qualname`.
  - **`agentforge_core.resolver.discover`** — entry-point scanner:
    - `discover_entry_points(resolver, force=False)` walks all
      `agentforge.*` groups via `importlib.metadata.entry_points()`,
      registers each as `(category=group_suffix, name=ep.name,
      cls=ep.load())`, and caches `ModuleInfo` per entry.
    - `ensure_discovered(resolver)` — lazy hook the resolver's own
      methods call, so discovery runs once per process without an
      explicit bootstrap.
    - `reset_discovery()` — for tests that install fake entry
      points or want a fresh scan.
    - Conflict handling: first-wins, WARN logged via
      `agentforge.resolver`. Load failures and non-class targets
      are skipped with WARN, not fatal.
  - **`Resolver.list_installed(category=None) -> list[ModuleInfo]`**
    returns every registered module with provenance metadata.
  - **`Resolver.clear()`** semantics adjusted — empties the
    registry only; call `reset_discovery()` separately for a fresh
    entry-point scan. The old behaviour would have broken tests
    that rely on import-time `@register` decorators.
  - Top-level re-exports from `agentforge_core`: `ModuleInfo`,
    `discover_entry_points`, `reset_discovery`.

  *New in `agentforge`:*
  - **`agentforge.cli`** subpackage — argparse-based CLI
    dispatcher. No third-party CLI dep.
  - **`agentforge list modules [--category <cat>] [--json]`**
    command — triggers the resolver's discovery and prints a
    grouped-by-category text table (or JSON list of `ModuleInfo`).
    Entry-point sources are annotated with their package + version;
    `@register`-only classes show as `(in-process)`. Empty
    registry prints a remediation hint.
  - **`[project.scripts]` entry point**:
    `agentforge = "agentforge.cli.main:main"`. Uses uv's existing
    console-script machinery — no extra deps.

  *Knock-on docs updates (forward-ref sweep per AGENTS.md rule):*
  - `feat-003` (LLM providers) — custom-provider runbook entry
    rewritten: feat-010 has now shipped the auto-load mentioned as
    the deferred dependency.
  - `feat-004` (Tools) — "Entry-point auto-loading of third-party
    tool packages" moved out of "What's not yet implemented" with
    a note pointing to `agentforge list modules`.
  - `feat-006` (Evaluators) — "String-name resolution... needs
    feat-010" reworded to note the resolver work is now done; only
    the Agent-level wiring for `evaluators=[...]` strings remains.

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
