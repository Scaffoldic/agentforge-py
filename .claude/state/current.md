---
feature: feat-004-tools-system
state: analysing
branch: feat/004-tools-system
started_at: 2026-05-10T14:00
last_milestone_at: 2026-05-10T14:00
last_shipped: feat-005 (Persistence) shipped via PRs #5 (sqlite + RAG), #7 (graph + neo4j + surrealdb), #8 (postgres); chore PR #9 (self-contained project layout) merged at 74ea4ed
blocker: null
flags_for_user: ["design-awaiting-approval"]
---

## Active feature

[`feat-004 — Tools system`](../../docs/features/feat-004-tools-system.md)

Per pipeline §1: lowest-numbered `proposed` feature with all
dependencies shipped. feat-004 depends only on feat-001 (✓). Two
other features are also eligible (feat-007, feat-008) — feat-004
wins by number.

## Scope (from canonical spec §4)

The locked `Tool` ABC already shipped under feat-001
(`agentforge_core.contracts.tool`). feat-004 layers on:

1. **`@tool` decorator** — wraps a typed function as a `Tool`
   subclass with `name` / `description` / `input_schema` inferred
   from signature + docstring. Pydantic model built from type hints
   (required vs optional from defaults). Description parsed from
   Google-style docstring.
2. **Default tools** shipped with `agentforge`:
   - `calculator` — arithmetic via Python AST evaluator (no `eval`)
   - `file_read` — read a file from a sandboxed working dir
   - `web_search` — pluggable search backend; DuckDuckGo HTML
     default (with warning when it breaks)
   - `shell` — sandboxed subprocess (`shell=False`, command-list
     only); **destructive** capability declared
3. **Capability vocabulary**: `{"filesystem", "network", "shell",
   "destructive"}` — declared per tool. Used by future safety
   guardrails (feat-018).
4. **Tool dispatch enhancements** in strategies' tool-call path:
   - `Tool.input_schema.model_validate(arguments)` before calling
     `run()`; ValidationError → observation step (LLM sees the
     error, not a stack trace)
   - Tool exceptions and timeouts → observation steps too
   - Optional per-tool `timeout_s` (default 30s, config-driven)
5. **Test isolation**:
   - `FakeTool.fake(name, fn)` — replace any tool with a stub
     during tests
   - Optional record/replay helper (feat-016 may extend this)

Out-of-scope (deferred):
- Entry-point auto-loading of third-party tools — that's feat-010
- MCP bridging — feat-013
- Cost attribution per tool — feat-009 (Observability)
- Tool-level rate limiting — feat-018 (Safety)

## Dependencies

- feat-001 (✓) — `Tool` ABC, `ToolCall`, `ToolSpec`, `Step`
- feat-002 (✓) — strategies that call tools (ReAct + others)

## Open design questions to resolve before implementing

- **Where does `@tool` live?** Spec §4.2 puts it at
  `agentforge.tool_decorator`. Proposal:
  `agentforge/_tools/decorator.py` and re-export from `agentforge`
  so `from agentforge import tool` works.
- **Docstring format**: start with Google-style only. NumPy can
  land later if asked.
- **`shell` tool security**: default to no-shell, command-list-only
  execution (`subprocess.run([...], shell=False)`). No glob
  expansion, no env-var interpolation. Document as "destructive —
  deploy with caution".
- **`web_search` default backend**: pluggable `search_fn`;
  DuckDuckGo HTML default with a clear warning if it breaks. Real
  backends (Serper, Tavily) ship as separate module packages later.
- **Timeout default**: 30s. Per-tool override at construction OR
  config.

## Proposed chunks (5–6 total)

1. **`@tool` decorator** — signature inference, Google docstring
   parser, Pydantic model builder, `Tool` subclass synthesis. Unit
   tests covering: simple types, optional defaults, complex types
   (list, dict, Pydantic-nested), missing type hint error,
   docstring parser edge cases.
2. **Default tools — `calculator` + `file_read`** — pure-Python,
   no I/O risks. AST-based calculator. file_read with working-dir
   sandbox + size cap.
3. **Default tools — `shell` + `web_search`** — subprocess sandbox
   for shell; pluggable search backend with DuckDuckGo default.
   Capabilities declared. Live integration tests gated on
   `RUN_LIVE_WEB=1`.
4. **Tool dispatch enhancements** — validation → observation,
   timeout, capability check honesty. Updates the strategies'
   `_call_tool` helper (or wherever the dispatch sits).
5. **Test isolation** — `FakeTool.fake()` API. Goes in
   `agentforge._testing` (alongside `FakeLLMClient`).
6. **CHANGELOG + Implementation section + PR** — update
   `docs/features/feat-004-tools-system.md` Implementation status,
   `CHANGELOG.md`, raise PR.

## TODO before next milestone

- [ ] User approves this analysis + chunk plan.
- [ ] On approval: state → `designing`, then `implementing`; begin
      chunk 1.
