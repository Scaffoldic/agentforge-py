# Development log — append-only

This file is the chronological history of the AgentForge framework's
development. Every milestone, every shipped feature, every bug-carry
across features lands here. Newest entries at the bottom.

Format: `## YYYY-MM-DDTHH:MM — <event>` followed by 1-5 lines of detail.

---

## 2026-05-09T18:00 — Documentation phase complete

20 features specified, 20 ADRs locked, 5 design docs written, doc
templates and dev-pipeline scaffolding in place. Old EVA docs archived
under `docs/archive/`. Repo state: design-only, no code yet.

Files added in this phase:
- `docs/README.md`
- `docs/design/architecture.md`
- `docs/design/design-principles.md`
- `docs/design/module-system.md`
- `docs/design/persistence-and-orm.md`
- `docs/design/scaffolding-and-upgrade.md`
- `docs/design/open-source-framework-plan.md` (legacy from naming exploration)
- `docs/features/README.md` (catalogue)
- `docs/features/feat-001` … `docs/features/feat-020`
- `docs/adr/README.md`
- `docs/adr/0001` … `docs/adr/0020`
- `.claude/templates/` (feature, design, architecture, adr, bug, enhancement)
- `.claude/CLAUDE.md`
- `.claude/development-pipeline.md`
- `.claude/standards/` (coding, testing, docs, git, configuration)
- `.claude/checklists/` (pre-feature, pre-commit, pre-pr, feature-complete)
- `.claude/state/` (README, current, log)
- `AGENTS.md` (repo root)

State: `idle`. Awaiting user signal to begin feat-001 implementation.

---

<!-- Append new entries below this line. Do not edit prior entries except
     to correct factual errors with a `(corrected YYYY-MM-DD: ...)` annotation. -->

## 2026-05-09T19:30 — Structural decisions locked

User confirmed:

- **TS scoping: `@agentforge/*` (scoped on npm).** PyPI stays flat.
  (ADR-0002 updated.)
- **Repo structure: two separate language repos** — `agentforge-py`
  (uv workspaces internally) and `agentforge-ts` (pnpm workspaces
  internally). The current `ai-agents/` is the design workspace; each
  language implementation lives in its own repo. (ADR-0002 updated.)
- **TS scaffolding: native TS port** of the same template format Copier
  consumes. Two engines, one template source of truth, shared test
  fixtures. TS users have no Python dependency. (ADR-0021 added;
  ADR-0005 updated; feat-011 §4.4, §4.9, §6, §8 updated.)
- **AGENTS.md hard cap: 200 lines.** CI-enforced.
- **License: Apache 2.0** (ADR-0016 was already accepted).
- **Python minimum: 3.13.**
- **Library adoption rule** — deep-dive a library's official docs and
  best-practices before adding it as a dependency. Documented in
  `.claude/standards/coding.md`.

Files changed in this milestone:
- `docs/adr/0002-multi-language-python-typescript.md` (locked decisions in §4)
- `docs/adr/0005-copier-not-cookiecutter-for-scaffolding.md` (TS reference updated)
- `docs/adr/0021-native-typescript-scaffolding-engine.md` (new)
- `docs/adr/README.md` (added 0021)
- `docs/features/feat-001-core-contracts-and-agent.md` (TS scoping locked)
- `docs/features/feat-011-scaffolding-and-upgrade.md` (TS engine locked, §4.4 §4.9 §6 §8 §10 updated)
- `.claude/standards/coding.md` (library deep-dive rule)
- `.claude/state/current.md` (cleared flags_for_user; recorded decisions)
- This log entry.

State stays `idle`. Next user signal advances to feat-001 implementation.

## 2026-05-09T20:00 — feat-001 started

Branch: `feat/001-core-contracts-and-agent` (in `python/agentforge-py/`).

Bootstrap commit on main: `6692d64` — uv workspace, Apache 2.0,
member packages `agentforge-core` (Tier 1) and `agentforge` (Tier 2),
GitHub Actions CI, pre-commit config, AGENTS.md, all empty src/ ready
for feat-001 to fill.

Bootstrap committed with `--no-verify` because no .py code yet exists
for the hooks to run against. **This is the only authorised
`--no-verify` use** (per AGENTS.md rule #9 + git standards). Future
commits go through the full hook.

## 2026-05-09T21:00 — Design approved; remote at github.com:Scaffoldic/agentforge-py.git

User approved the design (Pydantic v2 frozen models, ULID for
run_id / Claim.id, pyyaml for partial config loader, error class
hierarchy as proposed). User also created the remote at
`git@github.com:Scaffoldic/agentforge-py.git`.

Bootstrap commit on main (sha `6692d64`) pushed to remote main.
Currently on branch `feat/001-core-contracts-and-agent`.

## 2026-05-09T21:30 — feat-001 chunk 1 complete: production rails + value types

Landed (still uncommitted on the feat/001 branch — about to commit):
- `agentforge_core.production.{exceptions, budget, run_context, log_filter}`
- `agentforge_core.values.{messages, state, claim}`
- Updated `agentforge_core/__init__.py` to re-export the public API
- 7 unit-test files (100 tests including 1 Hypothesis property test)
- py.typed markers on both packages

Gate (all green, run via `uv run`):
- ruff format/check ✅
- mypy --strict ✅ (10 source files, no issues)
- bandit ✅
- pytest 100 passed ✅
- coverage 99.22% (gate is 90%) ✅

[BUG-CARRIED] bootstrap: placeholder `https://github.com/` URLs in
README, NOTICE, CHANGELOG, both member pyproject.toml files replaced
with the actual remote `github.com/Scaffoldic/agentforge-py`. Fixed
in this same feat/001 commit per `.claude/development-pipeline.md` §5.

[BUG-CARRIED] bootstrap: workspace root `pyproject.toml` had
`[tool.uv] dev-dependencies` (deprecated by uv 0.11) and didn't list
workspace members as deps — `uv sync` did not install them. Migrated
to `[dependency-groups] dev` and added `agentforge-core` /
`agentforge` as root deps with `[tool.uv.sources]` workspace = true.

Next chunks queued (still on this branch):
- chunk 2: core contracts (LLMClient / Tool / ReasoningStrategy /
  MemoryStore / Evaluator / Finding Protocol) + ABC tests.
- chunk 3: InMemoryStore + memory conformance suite + tests.
- chunk 4: resolver + Agent orchestrator + integration tests +
  config loader.
- chunk 5: docs polish + CHANGELOG finalisation pre-PR.

## 2026-05-09T23:30 — feat-001 PR raised

PR: https://github.com/Scaffoldic/agentforge-py/pull/1

5 commits on the branch (squash-merge to main per
`.claude/standards/git.md`):

  da9bc60 — production rails + value types
  f630c69 — core contracts (ABCs + Finding Protocol)
  2d04ecb — InMemoryStore + memory conformance suite
  09af2b5 — Agent orchestrator + resolver + config loader
  b5bd8e1 — CHANGELOG finalisation

Final tally:
  - 192 tests (174 unit + 2 integration + 1 conformance + 2 property)
  - Coverage on diff: 94.28% (gate is 90%)
  - mypy --strict: 28 source files, 0 issues
  - ruff format + check: clean
  - bandit -c pyproject.toml: clean
  - All commits pass the full pre-commit gate

State: `pr-raised`. Awaiting review + merge. On merge:
  - Switch to main, pull
  - Mark feat-001 status `shipped` in `docs/features/feat-001-*.md`
  - Mark feat-001 `shipped` in `docs/features/README.md` catalogue
  - Reset state to `idle` and pick next feature.

## 2026-05-09T20:30 — feat-001 analysis + design complete

State advanced to `designing`. Full analysis and design proposal in
`.claude/state/current.md`:

- Scope locked to: locked ABCs in `agentforge-core` (LLMClient, Tool,
  ReasoningStrategy, MemoryStore, Evaluator, Finding Protocol);
  value types (AgentState, Step, RunResult, Message, ToolCall,
  ToolSpec, LLMResponse, TokenUsage, Claim, EvalResult); production-
  rails primitives (BudgetPolicy, RunContext, current_run,
  RunIdFilter, exception hierarchy); minimum resolver; InMemoryStore;
  Agent orchestrator with locked constructor surface; partial config
  loader.
- Out of scope (deferred): ReActLoop (feat-002), built-in tools
  (feat-004), provider clients (feat-003), Finding variants
  (feat-008), evaluators (feat-006), safety validators (feat-018),
  observability beyond RunIdFilter (feat-009).
- File layout proposed (see current.md "File-layout decisions").
- Test plan: per-package unit tests, workspace integration +
  conformance + property tests; 90% coverage gate via pre-commit.
- New core deps proposed: `python-ulid` (for run_id + Claim.id),
  `pyyaml` (for partial config loader).

Awaiting user approval (`flags_for_user: ["design-awaiting-approval"]`).
On approval, state advances to `implementing` and src/ files start
landing.

## 2026-05-09T23:30 — feat-001 PR raised, then merged

- PR #1: https://github.com/Scaffoldic/agentforge-py/pull/1
- 5 feature commits + 2 CI fixes (`88ba10d` ruff version pin,
  `4eb4928` bandit `-c pyproject.toml`) on the branch.
- Final tally: 192 tests, 94.28% coverage on diff, mypy --strict
  clean across 28 source files.
- Merged: agentforge-py main @ 9ea1033 (2026-05-09).

## 2026-05-09T23:55 — chore PR #2 raised + merged

- PR #2: https://github.com/Scaffoldic/agentforge-py/pull/2
- Decoupled agentforge-py from the parent design workspace —
  AGENTS.md / README / PR template / pre-commit comments rewritten
  as standalone. Zero `../../` references remain. Reasoning: the
  parent `ai-agents/` workspace contains the maintainer's generic
  dev practice (`.claude/` pipeline, standards, state tracking)
  that should not appear in the public OSS repo.
- Merged: agentforge-py main @ 0b065fb (2026-05-10).

## 2026-05-10T01:00 — feat-002 started

User directive: ship all four reasoning loops stable from v0.1 in
`agentforge` (no `agentforge-strategies-experimental` package).
Modern approach throughout — structured tool calls, signal-based
completion (stop_reason), typed Pydantic plans, beam-search ToT,
supervisor-worker with proportional budget split.

Updates landed in the design workspace before branching:

- `docs/features/feat-002-reasoning-strategies.md` rewritten:
  - Title and metadata updated (all four stable; package =
    `agentforge` only)
  - §4.1 user-facing experience updated with all four strategies
  - §4.2 constructor signatures locked for all four
  - §4.3 modern internal mechanics for each strategy
    (ReAct via stop_reason, Plan-Execute with typed Plan,
     ToT with beam search, MultiAgent with proportional budget)
  - §4.4 module packaging — all four ship in `agentforge`
  - §7 test strategy expanded — conformance + AST + cost
    accounting + property + live (post feat-003)
  - §10 references to ReAct / Plan-and-Solve / ToT / Anthropic
    "Building effective agents" papers
- `docs/features/README.md` catalogue:
  - feat-002 row updated; 0.1 milestone now lists all four loops
    shipped stable; 0.3 milestone no longer mentions "experimental
    strategies"
- `docs/design/architecture.md` module catalogue:
  - Removed `agentforge-strategies-experimental` row (replaced
    with a comment noting all four loops ship in `agentforge`)

Branch: `feat/002-reasoning-strategies` (in `python/agentforge-py/`).

## 2026-05-10T01:30 — feat-002 analysis + design proposal complete

State `designing`. Full design in `.claude/state/current.md`:

- Scope: 4 reasoning strategies stable, modern primitives, shared
  `_StrategyBase`, FakeLLMClient test helper.
- File layout under `packages/agentforge/src/agentforge/strategies/`
  proposed (one file per strategy + `_base.py` + `_scoring.py`).
- Plan/PlanStep + WorkerSpec/WorkerPlan Pydantic types defined.
- 6-chunk commit plan (shared infra → ReAct → Plan-Execute →
  ToT → MultiAgent → conformance + property tests + docs).
- Test plan covers unit, integration, conformance (AST
  guardrail-call check), property (budget invariants), live
  (deferred to post-feat-003 with Bedrock).

Awaiting user approval (`flags_for_user: ["design-awaiting-approval"]`).

## 2026-05-10T00:00 — state reset to idle

feat-001 fully shipped + cleanup chore merged. Awaiting next-feature
signal from the user. Eligible candidates on the v0.1 critical path
(per `docs/features/README.md` — all `proposed`, dependencies on
feat-001 satisfied):

  feat-002 — Reasoning strategies (ReAct stable + 3 experimental)
  feat-003 — LLM & embedding providers
  feat-004 — Tools system (`@tool` decorator + default tools)
  feat-007 — Production rails wiring (FallbackChain, idempotency tools)
  feat-008 — Findings & output shapes
  feat-011 — Scaffolding & upgrade (`agentforge new`)
  feat-012 — Configuration system (full schema)
  feat-016 — Testing framework (`MockLLMClient` etc.)
  feat-017 — CLI runtime (`agentforge run`, …)
  feat-019 — Developer experience (runbooks + AGENTS.md template)

## 2026-05-10T05:00 — feat-002 shipped
PR #3 merged. Branch `feat/002-reasoning-strategies` deleted local + remote.
All four reasoning strategies stable in `agentforge.strategies`.
Coverage on diff: 92.4%.

## 2026-05-10T07:00 — feat-003 shipped (Bedrock first-party Tier-3)
PR #4 merged. Branch `feat/003-bedrock-provider` deleted.
`agentforge-bedrock` ships with caching / thinking / streaming /
embeddings; cross-region inference profiles supported transparently.

## 2026-05-10T08:00 — [DIVERGENCE BEGINS] feat-007 (memory + RAG) shipped under WRONG number
PR #5 merged on branch `feat/007-memory-and-rag`. **This work
actually implements canonical feat-005 (Persistence — `MemoryStore`
ABC + sqlite driver) plus extensions:** new `VectorStore` ABC +
value types + `run_vector_conformance`; new `InMemoryVectorStore`,
`Retriever`, `Agent(retriever=...)` kwarg + `RuntimeContext.retriever`;
new `agentforge-memory-sqlite` package (`SqliteMemoryStore` +
`SqliteVectorStore`).

**Why the wrong number was used:** the previous AI session was
disconnected from the canonical feature catalogue at
`docs/features/README.md` (parent workspace) — chore PR #2 had
removed `../../` cross-references but did not move the catalogue
into agentforge-py. With no local catalogue and a stale
`state/current.md`, the session invented `feat-007` from
CHANGELOG/roadmap memory. No log entry was written at the time.

## 2026-05-10T10:00 — [DIVERGENCE CONTINUES] roadmap PR #6 merged
docs PR adding feat-008 (postgres) + feat-009 (GraphStore) entries
to `agentforge-py/docs/roadmap.md` — both using **invented numbers**,
not canonical. Canonical feat-008 is "Findings & output shapes" and
canonical feat-009 is "Observability"; both still unshipped.

## 2026-05-10T11:00 — [DIVERGENCE] feat-009 (GraphStore + Neo4j + SurrealDB) shipped under WRONG number
PR #7 merged on branch `feat/009-graph-store`. **Actually implements
more of canonical feat-005:** new `GraphStore` ABC + value types +
`run_graph_conformance`; new `InMemoryGraphStore`,
`Agent(graph_store=...)` kwarg + `RuntimeContext.graph_store`; new
`agentforge-memory-neo4j` package (`Neo4jGraphStore` +
`Neo4jMemoryStore` over the official `neo4j` async driver); new
`agentforge-memory-surrealdb` package (`SurrealGraphStore` +
`SurrealVectorStore` + `SurrealMemoryStore` — tri-modal).

## 2026-05-10T12:00 — [DIVERGENCE] feat-008 (postgres) PR opened under WRONG number
PR #8 opened on branch `feat/008-postgres`. **Actually implements
final piece of canonical feat-005:** new `agentforge-memory-postgres`
package (`PostgresMemoryStore` + `PostgresVectorStore` over asyncpg
+ pgvector with HNSW index). Currently OPEN; will be rebased onto
the chore-self-contained-project-docs PR before merge.

## 2026-05-10T12:30 — divergence detected; remediation chosen
User caught the discrepancy on review. Adopted "Add mapping +
addendum" remediation (over renumbering history). Concrete actions
taken in PR #8 commit `a88977f`:

- Canonical `feat-005-persistence-and-memory.md` spec gained an
  Implementation status section with the full mapping table
  (shipped label → canonical → PR → scope delivered).
- `feat-001`, `feat-002`, `feat-003` specs gained Implementation
  status sections too (these matched canonical numbers).
- `agentforge-py/docs/roadmap.md` rewritten with a numbering note,
  shipped table, and backlog reorganised under canonical numbers.
- `agentforge-py/AGENTS.md` Workflow section gained two rules:
  branch `<NNN>` must match canonical feat-NNN spec; every feature
  PR updates the matching spec's Implementation section before
  merge.

## 2026-05-10T13:00 — chore-self-contained-project-docs started
Branch: `chore/self-contained-project-docs` (off main, off PR #8).

User identified the structural root cause: agentforge-py's
`.claude/CLAUDE.md` reading order references files that no longer
exist locally after PR #2 decoupled but did not move. AI sessions
working in agentforge-py couldn't find the canonical pipeline /
feature catalogue / state record.

Fix: each project becomes fully self-contained. Parent workspace
keeps the meta layer (universal pipeline, design principles, ADRs);
each sub-project owns its own feature specs, state, CHANGELOG,
AGENTS.md, CLAUDE.md. This PR moves `docs/features/` and
`.claude/state/` into agentforge-py.

## 2026-05-10T13:30 — chore-self-contained-project-docs PR raised
PR: https://github.com/Scaffoldic/agentforge-py/pull/9
Branch: `chore/self-contained-project-docs`. Awaiting review + merge.

## 2026-05-10T13:50 — chore PR #9 shipped
Merged at commit `74ea4ed`. Project is now fully self-contained for
OSS contributors. Workspace hosts the universal pipeline + shared
templates only; no project-specific content at workspace level.
Branch deleted local + remote.

## 2026-05-10T14:00 — feat-004 started
Branch: `feat/004-tools-system` (off main).
State: `analysing`. Pipeline rule §1 picks lowest-numbered proposed
feature with deps shipped — feat-004 (Tools) wins (deps: feat-001
✓). Awaiting user approval of analysis + chunk plan in
`state/current.md`.

## 2026-05-10T14:30 — feat-004 chunk 1 done: @tool decorator
Commit: `6ec7c13`. 25 unit tests pass via pre-commit gate.
`agentforge._tools.decorator.tool` re-exported as `from agentforge
import tool`. Bare and parameterised forms both work; Google-style
docstring parser feeds Pydantic Field descriptions. Decoration-time
errors on missing type hints / variadic / positional-only params.

## 2026-05-10T15:30 — feat-004 chunk 2 done: calculator + file_read
Commit: `97e2acc`. 36 unit tests across both tools (calculator's
AST-based safe evaluation; file_read's sandbox + size cap).

## 2026-05-10T16:00 — feat-004 chunk 3 done: shell + web_search
Commit: `c5be0f5`. 26 unit tests + a live integration test gated on
RUN_LIVE_WEB. shell uses asyncio.create_subprocess_exec (shell=False)
with timeout, output cap, optional whitelist. web_search ships a
pluggable backend with DuckDuckGo HTML default.

## 2026-05-10T16:30 — feat-004 chunk 4 done: tool dispatch
Commit: `20c9dc6`. Centralised _dispatch_tool helper on _StrategyBase
handles validation → observation, timeout, exception → observation
per spec §4.3. ReActLoop and PlanExecuteLoop refactored. 8 unit
tests lock the contract.

## 2026-05-10T17:00 — feat-004 chunk 5 done: FakeTool
Commit: `4ac290a`. agentforge._testing.FakeTool.fake() — minimal
scripted-response Tool for unit tests. 10 unit tests.

## 2026-05-10T17:15 — feat-004 chunk 6 done: docs + PR
Updated docs/features/feat-004 Implementation status, CHANGELOG,
roadmap (moved feat-004 from backlog to shipped). Pre-commit hook
ID migrated from `ruff` (legacy alias) to `ruff-check`.

## 2026-05-10T17:25 — feat-004 shipped
PR #10 merged at `2b1a37c`. Branch deleted local + remote.
Six chunks landed cleanly: @tool decorator, calculator + file_read,
shell + web_search, _dispatch_tool helper + ReAct/PlanExecute
refactor, FakeTool test helper, docs + ruff hook id migrate.

## 2026-05-10T17:30 — feat-007 started
Branch: `feat/007-production-rails`. State: `analysing`.

User question on scope: "production rails covers all modern
guardrails, cost, budget, security etc". Clarified canonical
split: feat-007 is narrower (cost budget + run_id +
idempotency + FallbackChain). Modern security guardrails are
feat-018 (Safety). Observability is feat-009.

Most of feat-007 already shipped under feat-001 (BudgetPolicy,
RunContext, current_run, idempotency_key_for, RunIdFilter). Only
remaining piece: FallbackChain. User picked "Ship feat-007
(FallbackChain only) — small (Recommended)".

Chunk plan (3 total) in state/current.md awaiting approval.

## 2026-05-10T17:50 — Runbook policy locked in
User asked why runbooks aren't part of each feature PR. Reviewed
canonical model: per docs/README.md, runbooks live in the (yet-to-
exist) agentforge-templates repo and are owned by feat-019. Bootstrap
problem: features ship today without their developer-facing runbook
content; feat-019 would need to author 16 retroactively.

User's choice (locked):
1. **Inline `## Runbook` section in each feat-NNN spec.** When
   feat-011 + feat-019 ship, the templating engine consumes these
   sections into scaffolded agent projects. Single source of truth.
2. **Backfill** runbook sections for feat-001/002/003/004/005 in
   a separate `chore/backfill-runbooks` PR AFTER feat-007 ships
   (don't disrupt in-flight work).

Updates landed:
- AGENTS.md Workflow §: new rule "Every feature PR adds a
  `## Runbook` section in the matching canonical spec".
- memory feedback_workflow.md rule #8 added (audience: agent
  developers, not framework maintainers).
- state/current.md feat-007 chunk 3 expanded to include the
  Runbook section as part of the docs-update commit.

feat-007 chunk plan unchanged in count (still 3 chunks); chunk 3
just gains the Runbook authoring sub-task.

## 2026-05-10T18:30 — feat-007 chunks 1-3 done
- chunk 1 `6bdd066`: FallbackChain class + 23 unit tests
- chunk 2 `2e7d2d3`: top-level re-export + 4 Agent-integration tests
- chunk 3 (this): CHANGELOG, Implementation status, **first-ever
  Runbook section** (configure fallback / tune retries / combine
  with budget / read run_id from a tool / debug "every provider
  failed" / when not to use FallbackChain), roadmap moved feat-007
  from backlog to shipped.

PR #11 to be raised next.

## 2026-05-11T10:00 — feat-007 shipped, opening chore/backfill-runbooks
PR #11 (feat-007 FallbackChain) merged to main @ `f61ad44`. Synced
main, deleted `feat/007-production-rails` local + remote. Branched
`chore/backfill-runbooks` for the retroactive Runbook policy
application (task #76).

## 2026-05-11T10:30 — chore/backfill-runbooks ready for PR
Authored `## Runbook` sections on five shipped specs:
- feat-001 — minimum agent / budget caps / step trace / hooks /
  config / provider switching / sync shim
- feat-002 — strategy picker / tuning ReAct / Plan-Execute
  replanning / ToT judge scorer / MultiAgentSupervisor
- feat-003 — Bedrock setup / cross-region profiles / caching /
  thinking / embeddings / cost / custom provider registration
- feat-004 — `@tool` decorator / locking down shell + file_read /
  `FakeTool` / timeouts / step inspection
- feat-005 — backend picker / sqlite / postgres / neo4j / surrealdb /
  RAG via Retriever / namespacing / init_schema / live tests

Also fixed a stale `Agent(budget=BudgetPolicy(...))` example in
feat-007's existing runbook — the constructor takes `budget_usd=`
+ `max_iterations=`, not `budget=`. Same form used in feat-001
runbook from the start.

Pre-commit gate green (doc-only diff). CHANGELOG entry added under
`[Unreleased] / Docs`. PR to be raised next.

## 2026-05-11T11:00 — forward-reference hygiene added to chore PR
User flagged that the backfilled runbooks reference unshipped
features (feat-006/011/012/018/020 + backlog provider/tool packs)
and asked how those get cleaned up when the dependencies ship.

Adopted "mechanism by policy" — runbook content stays as-is
(forward references are useful signposts today), with two
guardrails to prevent rot:

1. **AGENTS.md** gets a workflow rule — every feature PR runs
   `git grep -nE 'feat-NNN|<backlog-pkgs>' docs/features/*.md`
   for its own number plus any backlog packages it ships, and
   updates every match so existing runbooks reflect the now-
   shipped surface.
2. **`.claude/checklists/pre-pr.md`** gains the same line as a
   blocking item under "Documentation complete".
3. The "Audience…When feat-011 / feat-019 ship…" preamble on
   every runbook (6 specs: feat-001/002/003/004/005/007) is
   rephrased tense-neutral so it doesn't decay if feat-011/019
   slip. New form: "This is the canonical home for the feature's
   runbook; feat-011 / feat-019 consume these sections into
   scaffolded agent projects."

CHANGELOG addendum under the same `[Unreleased] / Docs` entry.

## 2026-05-11T11:30 — PR #12 merged, picking up feat-008
PR #12 (chore/backfill-runbooks + hygiene policy) merged to main @
`b173d31`. Synced main, deleted `chore/backfill-runbooks` local +
remote.

Picked up **feat-008 (Findings & output shapes)** per pipeline §1.
Deps: feat-001 ✓ (Finding Protocol already shipped). Branched
`feat/008-findings-and-output-shapes`.

Drafted design analysis + 4-chunk plan in `state/current.md`:
1. Variants (Simple/Patch/Narrative/MultiSpan) + helper types
   (Patch, Span) in `agentforge.findings` as frozen Pydantic v2
   models (ADR-0014).
2. `FindingRenderer` ABC in core + `RendererRegistry` in runtime
   (most-specific-wins dispatch).
3. Four built-in renderers (scorecard / patch-applier / markdown /
   span-table) + `RendererRegistry.default()` factory.
4. Implementation status + Runbook + CHANGELOG + roadmap + PR +
   forward-reference sweep per the AGENTS.md rule added in PR #12.

State: `design-analysis` / `awaiting-design-approval`. Awaiting
user sign-off on the chunk plan before implementation begins.

## 2026-05-11T11:45 — feat-008 design approved
User approved Pydantic-v2-frozen-models choice over the spec's
`@dataclass` sketch (per ADR-0014). Beginning implementation.

## 2026-05-11T12:00 — feat-008 chunk 1 done
`bfb8c33` — `Patch`, `Span`, `SimpleFinding`, `PatchFinding`,
`NarrativeFinding`, `MultiSpanFinding` as frozen Pydantic v2 models
in `agentforge.findings`. `_FindingBase` internal base provides
`to_dict` / `from_dict` plumbing. 19 unit tests pass; Protocol
`isinstance` check works for all variants including a third-party
custom Pydantic model. Top-level re-exports added.

## 2026-05-11T12:30 — feat-008 chunk 2 done
`4f5e95c` — `FindingRenderer` ABC at
`agentforge-core/contracts/renderer.py` (re-exported from
`agentforge_core`); `RendererRegistry` at
`agentforge/renderers/registry.py` with most-specific-wins
dispatch by isinstance, ties broken by registration order;
`MissingRendererError`. 9 unit tests cover exact-type match,
missing-error, subclass-wins in both registration orders, tie-
break via re-registration, registration order preservation,
format passthrough, top-level re-export. `.default()` factory
deferred to chunk 3.

## 2026-05-11T12:45 — feat-008 chunk 3 done
`26b5da7` — Four built-in renderers in `agentforge/renderers/`:
`ScorecardRenderer` (SimpleFinding), `PatchApplierRenderer`
(PatchFinding), `MarkdownRenderer` (NarrativeFinding),
`SpanTableRenderer` (MultiSpanFinding). All support text +
markdown formats; unknown format raises ValueError, wrong variant
raises TypeError. `_defaults.populate_defaults(registry)` helper +
`RendererRegistry.default()` factory pre-populates all four. 21
unit tests including end-to-end dispatch through `.default()` and
in-place built-in override. Top-level re-exports added.

## 2026-05-11T13:00 — feat-008 chunk 4 done, PR pending
- `docs/features/feat-008-findings-and-output-shapes.md`:
  metadata status → `shipped (Python)`; added Implementation
  status section (chunk table + deviations: Pydantic models not
  `@dataclass`, `Patch.hunk_count` field added, Span line-order
  invariant, internal `_FindingBase` plumbing; not-yet:
  `Claim.from_finding`, polymorphic `Finding.from_dict`, HTML
  renderers, streaming emission, TS port); added Runbook section
  (8 task entries from "how do I emit" through "when not to use"
  + "how do I render a list of findings").
- `CHANGELOG.md`: `[Unreleased] / Added` entry with full surface
  catalogue.
- `docs/roadmap.md`: feat-008 row moved from "Backlog" to
  "Shipped".
- `docs/features/README.md` catalogue: feat-008 status updated
  `proposed` → `shipped (Python)`.
- **Forward-reference sweep**: feat-005's §4.1 example imports
  `SimpleFinding` (now real) and `Claim.from_finding(...)` (still
  not implemented — feat-005 follow-up, documented in feat-008
  Implementation section). feat-006/014/015/016 reference
  `Finding` / `SimpleFinding` in design sections — those features
  are still unshipped; their own PRs will refresh forward-tense
  language at ship time per the AGENTS.md rule.

Ready to push and raise PR.

## 2026-05-11T13:30 — feat-008 merged @ #13; picking up feat-006
User approved single-PR scope for feat-006 (target version 0.2,
spans both `agentforge` and new `agentforge-eval-geval` package).
Branched `feat/006-evaluators-and-benchmarks` and drafted 8-chunk
plan.

## 2026-05-11T14:00 — feat-006 chunks 1-5 done (runtime + 4 deterministic graders)
- chunk 1 `87bd0f2`: `RunResult.eval_scores` tuple field +
  `Agent._run_evaluators` loop (budget-gated; WARN logs skips via
  `agentforge.evaluators` logger). Closes the feat-001 gap where
  `evaluators=[...]` was accepted but never iterated.
- chunk 2 `93b241a`: `Coverage` deterministic grader.
- chunk 3 `6938866`: `FormatCompliance` (regex / pydantic_model /
  json_parseable; multi-mode rejected at construction).
- chunk 4 `3bad0bd`: `RegressionVsBaseline` (JSONL baseline; exact +
  structural modes; `no_baseline` label with NaN score).
- chunk 5 `8689b44`: `Consistency` (caller-supplied async runner;
  agreement fraction; custom matcher; runner failure → fail label).

## 2026-05-11T15:30 — feat-006 chunks 6+7 done (geval package)
`f771791` — new workspace member `agentforge-eval-geval`:
- `GEval` engine: rubric (dict or YAML), defensive JSON parsing,
  budget commit via `contextlib.suppress`, score clamping to [0, 1].
- 6 named graders: Correctness, Faithfulness, Groundedness,
  Hallucination, Relevance, Helpfulness. Each loads a shipped YAML
  rubric from `rubrics/`.
- 6 versioned rubric YAMLs (criteria + scoring; some with `inputs`).
- Entry-point registration under `agentforge.evaluators`.
- Workspace + CI + pre-commit extended in lockstep with new mypy /
  bandit / pytest paths (the AGENTS.md drift-trap rule applies).
- 30 unit tests covering engine + grader dispatch.

## 2026-05-11T16:00 — feat-006 chunk 8 done, PR pending
- `docs/features/feat-006-evaluators-and-benchmarks.md`: status →
  `shipped (Python)`; added Implementation status (chunk table +
  deviations: eval_scores tuple not dict; format_compliance modes
  ≠ spec's grammar; regression semantic deferred; consistency
  uses caller-runner not auto-Agent; G-Eval cost commit best-
  effort; no CLI here — feat-017). Added Runbook section (10
  task entries: attach graders, pick deterministic vs LLM-judge,
  budget gating, cheap judge for expensive agent, custom rubric,
  baseline scoring, consistency, reading EvalResults, debugging
  "never ran", when not to use).
- `CHANGELOG.md` `[Unreleased] / Added`: full surface catalogue.
- `docs/roadmap.md`: feat-006 row moved from Backlog → Shipped.
- `docs/features/README.md`: feat-006 status `proposed` → `shipped`.
- **Forward-reference sweep**: feat-002's runbook + Implementation
  section rewritten — old text said "until feat-006 lands"; now
  acknowledges feat-006 shipped the post-run surface while ToT's
  in-strategy `scorer="judge"` is a separate follow-up.

Ready to push.

## 2026-05-11T16:30 — feat-006 merged @ #14; picking up feat-009
User approved single-PR scope, Option B — OTel only, vendor
packages (Langfuse / Phoenix / Evidently / StatsD) deferred to
follow-up sub-feats. Spec's own thesis backs it ("OTel is the wire
format"). Branched `feat/009-observability` and drafted 7-chunk plan.

## 2026-05-11T17:00 — feat-009 chunks 1-2 done
- chunk 1 `d369dc2`: closed long-standing gap — `Agent(on_step=...)`
  now actually fires (was accepted but ignored under feat-001).
  List-of-hooks fan-out for both on_step + on_finish; per-hook
  try/except isolation via `_safe_call_hook` (logs WARN through
  `agentforge.observability`); async hooks awaited.
- chunk 2 `ccee40d`: JSON log format — `JsonFormatter` +
  install/uninstall helpers in core; Agent wires when
  `logging.format == "json"` config.

## 2026-05-11T17:45 — feat-009 chunks 3-6 done
`7901253` — OTel surface end-to-end:
- core adds `opentelemetry-api` dep; new
  `agentforge_core/observability/tracing.py` with `get_tracer()`.
- `Agent.run` wraps the run in an `agent.run` span carrying
  run_id / task / finish_reason / cost / tokens / duration /
  n_steps.
- new `agentforge-otel` package: `OpenTelemetryHook(endpoint=,
  service_name=, sample_rate=, redact_fields=)` configures SDK +
  OTLP exporter on construction (idempotent; respects existing
  user-installed provider). Dispatches both `on_step` and
  `on_finish` via `__call__`. Step + tool-call events with
  key-based arg redaction (default: api_key, password, secret,
  token, authorization).
- Workspace + CI + pre-commit + mypy override extended in
  lockstep with the new package.
- Tests via OTel's `InMemorySpanExporter`.

## 2026-05-11T18:00 — feat-009 chunk 7 done, PR pending
- `docs/features/feat-009-observability.md`: status → `shipped
  (Python, OTel only)`; added Implementation status (7-chunk
  table; deviations: OTel-only scope, root span only — not
  full tree, key-based redaction not content-based, required
  service_name); added Runbook (8 task entries: add observability,
  emit JSON logs, fan out multiple backends, custom hook, redact
  secrets, keep cost low, read span attributes, vendor
  compatibility, when not to use).
- `CHANGELOG.md`: full `[Unreleased] / Added` entry for feat-009
  + knock-on note about feat-004 runbook update.
- `docs/roadmap.md`: feat-009 row moved Backlog → Shipped; new
  "feat-009 vendor-package sub-feats" section documents the four
  deferred packages.
- `docs/features/README.md`: feat-009 status updated.
- `docs/features/feat-004-tools-system.md`: "Cost attribution
  per tool — feat-009" moved out of "what's not yet" list with a
  note that feat-009 has shipped it via the OTel hook.

Ready to push.

## 2026-05-11T18:30 — feat-009 merged @ #15; picking up feat-010
User chose Option B — single PR, runtime side + read-only `list`
CLI. Destructive `add/swap/remove` CLI commands depend on feat-012
(Configuration system) for manifest application + config-schema
validation; deferred to follow-up sub-feat. Branched
`feat/010-module-discovery` and drafted 3-chunk plan.

## 2026-05-11T19:00 — feat-010 chunks 1-2 done
- chunk 1 `ece4195`: `ModuleInfo` value type, entry-point scanner
  (`agentforge_core.resolver.discover`), `Resolver.list_installed`.
  Lazy + cached scan; conflict first-wins + WARN; load failures
  isolated + WARN. `Resolver.clear()` no longer resets discovery
  (would have broken import-time `@register` decorators).
- chunk 2 `409067e`: `agentforge` CLI scaffold (`agentforge.cli.*`),
  `agentforge list modules` command with `--category` + `--json`,
  `[project.scripts]` entry point. argparse-based, no third-party
  CLI deps.

## 2026-05-11T19:30 — feat-010 chunk 3 done, PR pending
- `docs/features/feat-010-module-discovery-and-cli.md`: status →
  `shipped (Python — runtime + read-only list CLI)`; added
  Implementation status (3-chunk table; deviations: read-only
  scope, `list_available` deferred, `clear` semantics changed);
  added Runbook (6 task entries).
- `docs/features/README.md`: feat-010 row updated.
- `docs/roadmap.md`: feat-010 moved Backlog → Shipped; new
  "feat-010 destructive-CLI sub-feat" section documents deferred
  half.
- `CHANGELOG.md`: full feat-010 entry + knock-on notes.
- **Forward-reference sweep**: feat-003 / feat-004 / feat-006
  forward-tense feat-010 references rewritten to reflect shipped
  state.

Ready to push.

## 2026-05-11T20:00 — feat-010 merged @ #16; picking up feat-012
Flagged the feat-011-vs-feat-012 question (feat-011 declares
feat-010 as its dep but the half of feat-010 it actually consumes
was deferred; feat-012 is the realistic next pick to unblock
everything). User confirmed picking feat-012, then chose Option A —
full scope (target version 0.1, foundational). Branched
`feat/012-configuration-system` and drafted 11-chunk plan.

## 2026-05-11T20:45 — feat-012 chunks 1-6 done
`6a847b8` — schema + loader rework bundled:
- Moved schema + loader from `agentforge.config` to
  `agentforge_core.config` (runtime package re-exports for
  backward compat).
- Widened root: `BudgetConfig` (replaces flat `budget_usd`),
  `ModulesConfig`, `ProvidersConfig`, `OutputConfig`,
  `system_prompt_file: Path`.
- Loader features: layered env files (deep-merge dicts, list-
  replace) via `AGENTFORGE_ENV`; dotted-path overrides;
  `AGENTFORGE_CONFIG` + `AGENTFORGE_LOG_LEVEL` env shortcuts.
- Breaking YAML change: `agent.budget_usd` → `agent.budget.usd`
  (with `extra="forbid"` for a clean error). Locked
  `Agent(budget_usd=)` kwarg surface preserved.

## 2026-05-11T21:00 — feat-012 chunk 7 done
`c0d177a` — module-side schema integration:
- `cls.config_schema: ClassVar[type[BaseModel] | None]` convention.
- `validate_module_configs(cfg, resolver=None, strict=True)`
  walks `modules.*` blocks, resolves classes via the resolver,
  validates each `config:` dict.
- Lenient mode (`strict=False`) skips missing modules — for
  `agentforge config validate` against configs that reference
  packages installed elsewhere.

## 2026-05-11T21:15 — feat-012 chunks 8-10 done
`c088273` — `agentforge config` CLI:
- `validate [--path P] [--env E] [--override K=V]
  [--strict-modules]` — schema + module-schema validation;
  Pydantic errors rendered with dotted YAML paths.
- `show [--resolved | --raw]` — print loaded config as YAML.
- `schema [--indent N]` — emit root JSON Schema for editor
  autocomplete.

## 2026-05-11T21:30 — feat-012 chunk 11 done, PR pending
- `docs/features/feat-012-configuration-system.md`: status →
  `shipped (Python)`; added Implementation status (11-chunk
  table; deviations: breaking YAML budget change documented,
  evaluator string-shorthand deferred, Agent auto-wiring of
  modules.* deferred to feat-010 destructive-CLI follow-up);
  added Runbook (10 task entries: minimal YAML, modules, env
  vars, env overlays, CLI overrides, validate, show, IDE
  autocomplete, custom module schemas, log level, when not to
  use YAML).
- `CHANGELOG.md`: full feat-012 entry + knock-on notes.
- `docs/roadmap.md`: feat-012 row moved Backlog → Shipped.
- `docs/features/README.md`: feat-012 status updated.
- **Forward-reference sweep**: feat-001 / feat-003 / feat-004 /
  feat-006 forward-tense feat-012 references rewritten.

Ready to push.

## 2026-05-11T22:00 — feat-012 merged @ #17; picking up feat-010 destructive CLI
User chose Option A — destructive CLI before feat-011. feat-011
will consume the same manifest-apply machinery; shipping that
here means feat-011 stays scoped to scaffolding without
re-inventing the manifest format. Branched
`feat/010b-destructive-cli` and drafted 4-chunk plan.

## 2026-05-11T22:15 — feat-010b chunk 1 done
`dadc6c4` — pure-data applier layer:
- `Manifest` / `EnvVarEntry` / `TemplateFile` / `AppliedManifest`
  value types in `agentforge-core/values/manifest.py`.
- Idempotent `apply_manifest(...)`, `reverse_manifest(...)`,
  `read_applied(...)` in `agentforge.cli.manifest_apply`.
- 20 unit tests covering env-var append (idempotent), template
  copy with marker (per-extension comment style), refuse-overwrite
  for unmarked files (and the `overwrite=True` escape), config-
  block deep-merge into agentforge.yaml + reject list-top-level,
  state file write + round-trip, reverse env vars / templates /
  config block / state + tolerates already-deleted artifacts.

## 2026-05-11T22:30 — feat-010b chunks 2-3 done
`f2c323c` — `agentforge add/remove/swap module` commands:
- `agentforge add module <dist>` — pip install + manifest
  discovery (importlib.resources) + applier + next_steps print.
  Idempotent: re-run prints "already applied".
- `agentforge remove module <dist>` — reverse applier + pip
  uninstall. Tolerates the package being already-uninstalled
  (skips config-block reverse only).
- `agentforge swap <category> <from> <to>` — composes
  remove + add. NOT transactional; documented.
- Pip subprocess injected via `PipRunner` callable so tests don't
  hit the network. Production: `python -m pip`.
- 10 unit cases covering happy path, pip failure aborts before
  apply, missing manifest, idempotent re-add, remove happy path,
  no-state error, package-already-uninstalled, swap with separate
  package roots, swap helper composition, swap aborts on
  remove-failure.

## 2026-05-11T22:45 — feat-010b chunk 4 done, PR pending
- `docs/features/feat-010-module-discovery-and-cli.md`: status
  updated to "full surface"; Implementation section's chunk
  table extended; deviations list updated (drop the "single PR
  read-only only" line — no longer true); What's-not-yet-
  implemented list slimmed (only `list_available` PyPI query,
  `uv add` detection, EP cache invalidation, transactional
  swap, TS port remain).
- Runbook gains 6 new entries: add module in one command, write
  a module manifest, swap drivers, remove a module, idempotency
  / atomicity, where state lives + whether to commit.
- `CHANGELOG.md`: full feat-010-destructive entry.
- `docs/roadmap.md`: feat-010 row updated to mention both PRs;
  "feat-010 destructive-CLI sub-feat (deferred)" section
  removed (no longer deferred).
- `docs/features/README.md`: feat-010 catalogue row updated.

Ready to push.

---

## 2026-05-11T23:55 — feat-011 chunk 6 done, PR pending

All six chunks of feat-011 landed on `feat/011-scaffolding-and-upgrade`:

- `d07714e` — chunk 1: Copier dep + `agentforge new` + `minimal`
  template + 6 unit tests.
- `1207568` — chunk 2: `code-reviewer`, `patch-bot`, `docs-qa`,
  `triage`, `research` templates + parametrised smoke tests.
- `9ce6a5c` — chunks 3-5: `.agentforge-state/managed-files.lock`
  + per-extension marker headers + `agentforge upgrade` (Copier
  three-way merge) + `agentforge fork`/`unfork`/`status` + 23
  unit tests in `test_scaffold_state.py`.
- (about-to-commit) chunk 6: spec status set to shipped + §10
  Implementation status table + §11 Runbook;
  `docs/features/README.md` row updated; `docs/roadmap.md` moves
  feat-011 to shipped; CHANGELOG `[Unreleased] / Added` entry;
  state files refreshed.

Deviations from feat-011 §4.4 design recorded in spec §10:

- Templates ship in-wheel (`importlib.resources.files`-based),
  not a separate `agentforge-templates` repo. Hatchling
  force-include preserves the `{{project_slug}}/...` directory
  inside the wheel. Migration to a separate repo remains a
  small follow-up if independent template versioning matters.
- `unfork` is partially restorative — it re-prepends the
  marker and updates the lock; content re-render happens on the
  next `agentforge upgrade`.
- `--run-tests` flag on `upgrade` deferred until the test-runner
  integration (post-feat-019) lands.
- TypeScript engine (ADR-0021) deferred.

Tooling notes: templates contain Jinja-embedded `.py`/`.toml`
files plus a `{{project_slug.replace('-', '_')}}` directory that
isn't a valid Python package. Added
`packages/agentforge/src/agentforge/templates/` to the mypy
`exclude`, ruff `extend-exclude`, and global pre-commit `exclude`
so the gate doesn't try to parse them. Copier needs
`_templates_suffix: ""` to render file contents Cookiecutter-
style without forcing every file to be named `foo.py.jinja`.

Ready to push and raise PR #19.

---

## 2026-05-12T00:25 — feat-017 chunk 9 done, PR pending

All nine chunks of feat-017 landed on `feat/017-cli-runtime`:

- `34ffd7f` — chunk 1: `MemoryStore.delete()` on the ABC + every
  driver + conformance + `RecordRunHook` + `Agent(record_runs=)`.
- `c80f54f` — chunk 2: `ReplayLLMClient.from_recording` +
  `replay_tools` + `ReplayExhausted`.
- `1eeb6fb` — chunk 3: `build_agent_from_config` /
  `load_and_build` helpers resolving providers / memory /
  evaluators / strategy / tools via the global Resolver.
- `5e6fc7a` — chunk 4: `agentforge run` CLI with exit codes
  0/1/2/3/4 + plain/json/rich output + `--replay`/`--record`.
- `b5aebbc` — chunk 5: `agentforge eval --fixtures JSONL
  --threshold` with rich/json/junit output + exit 5 on threshold
  fail.
- `44e1f86` — chunk 6: `agentforge debug --replay RUN_ID` stdlib
  `cmd.Cmd` REPL.
- `f4d8b9b` — chunk 7: `agentforge db
  {migrate,backup,restore,purge,query}` + tiny `key:value` DSL.
- `98e4c85` — chunk 8: `agentforge health` preflight (renamed
  from spec's `status` to avoid feat-011 collision).
- (about-to-commit) chunk 9: spec status → shipped + §10
  Implementation table + §11 Runbook; features README + roadmap;
  CHANGELOG `[Unreleased]/Added`; state refreshed.

Locked decisions captured in spec §10:

- `__step` / `__eval` / `__run` are reserved category names —
  part of the v0.1 on-disk contract for replay.
- Exit codes: 0 success / 1 generic / 2 config invalid / 3
  budget exceeded / 4 guardrail tripped / 5 eval threshold not
  met.
- argparse, not Typer.
- Templates in-wheel; renamed `status` → `health`; `db migrate`
  no-op on driverless schemas; `unfork` partial restore (feat-011
  behaviour unchanged).
- TS engine, CI upgrade matrix, Windows CI, run-tests on
  upgrade — all deferred.

Tooling note: pyproject `filterwarnings` demotes ResourceWarning
+ PytestUnraisableExceptionWarning to non-error. Many
asyncio.run callsites in the test suite occasionally surface a
stale kqueue selector reference at interpreter shutdown on macOS;
the loops have actually been closed.

Ready to push and raise PR #20.

---

## 2026-05-12T01:30 — feat-016 chunk 5 done, PR pending

All five chunks of feat-016 landed on `feat/016-testing-framework`:

- `6c69bbe` — chunk 1: public `agentforge.testing` namespace +
  `MockLLMClient` (from_script / deterministic + `call_count` +
  `tool_calls_observed`) + re-exports of FakeTool / FakeLLMClient
  / echo_response.
- `72c4de5` — chunk 2: `agent_factory` (safe defaults including a
  single-step LLM-call strategy) + pytest fixtures (`mock_llm`,
  `temp_memory_store`) + conformance re-exports.
- `327e525` — chunk 3: `record_llm(real, path, redactions)` +
  `MockLLMClient.from_recording(path)` + `load_recording` +
  versioned JSONL header + default redactions (api_key /
  authorization / bearer) + recursive `_redact` over dicts/lists.
- `f007d1e` — chunk 4: new `agentforge-testing` workspace member
  (Tier-3) with `GoldenSetRunner`, `assert_snapshot`,
  `analyze_recording`. Root pyproject + .pre-commit + ci.yml
  extended.
- (about-to-commit) chunk 5: spec status → shipped + §10
  Implementation table + §11 Runbook; features README; roadmap;
  CHANGELOG `[Unreleased]/Added`; state refreshed.

Deviations captured in spec §10:

- `agentforge._testing` retained as compat shim for existing
  internal tests; new code uses `agentforge.testing`.
- `MockLLMClient` doesn't yet satisfy a hypothetical
  `run_llm_conformance` harness (none exists in core).
- Replay matches by sequence today (request_hash persisted but
  not consulted on replay).
- VCR full redaction pipeline deferred; basic redaction ships.
- TS port deferred (Python defines the cassette format).

Tooling note: two N818 noqa annotations on `GoldenMismatch` and
`SnapshotMismatch` — both subclass `AssertionError` so pytest
reports them naturally, which is more important than the Error
suffix.

Ready to push and raise PR #21.

---

## 2026-05-12T03:00 — feat-018 chunk 9 done, PR pending

All nine chunks of feat-018 landed on `feat/018-safety-guardrails`:

- `25abbf7` — chunk 1: ABCs + `ValidationResult` +
  `GuardrailPolicy` (in `config.schema` to dodge a cycle through
  `values.state`) + `GuardrailsConfig` / `GuardrailEntry`.
- `a7743cb` — chunk 2: built-in basics (`prompt_injection_basic`,
  `pii_redact_basic`, `capability_check`, `allowlist`) +
  auto-registration via importing `agentforge.guardrails` from
  `agentforge/__init__.py`.
- `0123cb4` — chunk 3: `GuardrailEngine` + Agent integration +
  `RunResult.guardrail_events` + `agentforge.audit` logger.
  Wrapping LLM + tools at runtime keeps strategies oblivious.
- `887079f` — chunk 4: conformance harnesses re-exported through
  `agentforge.testing`.
- `3b3bce7` — chunk 5: `agentforge-guard-llmguard` (LLM Guard
  scanner suite; inverts risk score; `<sanitized>` flows out via
  `redacted_content`).
- `6148298` — chunk 6: `agentforge-guard-presidio` (Presidio
  analyzer + anonymizer; `action: redact|score-only`; lazy
  `AnalyzerEngine` load).
- `529e54d` — chunk 7: `agentforge-guard-nemo` (NemoInput +
  NemoOutput; `config_path` directory or injected runner;
  Colang-DSL rails).
- `4415239` — chunk 8: `agentforge-guard-llamaguard` (Llama Guard
  3 over `LLMClient`; parses `safe` / `unsafe S1..S14`).
- (about-to-commit) chunk 9: spec status → shipped + §10
  Implementation table + §11 Runbook; features README; roadmap;
  CHANGELOG `[Unreleased]/Added`; state refreshed.

Vendor-module test pattern: each ships an inline fake runner in
its test module (not `conftest.py`) so the monorepo's root
conftest.py doesn't shadow it during the shared pre-commit
gate. Each fake mocks the upstream-SDK runner protocol; the real
runner lazy-imports the SDK and surfaces a clear ModuleError
with pip remediation when missing.

Tooling notes:
- mypy overrides for `llm_guard.*` / `presidio_analyzer.*` /
  `presidio_anonymizer.*` / `nemoguardrails.*` so the
  `import_not_found` errors don't break the strict gate.
- `Agent._build_runtime_metadata` helper extracted to keep
  `Agent.run` under ruff's PLR0915 statement cap.
- pyproject + .pre-commit + ci.yml extended in lock-step for
  every new workspace member.

Ready to push and raise PR #22.

---

## 2026-05-12T05:30 — feat-019 chunk 8 done, PR pending

All eight chunks of feat-019 landed on
`feat/019-developer-experience-and-ai-rules`:

- `85aaf70` — chunk 1: three-section managed/custom file
  format with `split_three_section` / `merge_three_section`
  helpers + the `<!-- agentforge:end-managed -->` /
  `<!-- agentforge:custom -->` markers.
- `58663de` — chunk 2: `inject_shared_scaffold` post-render
  hook walks `agentforge.templates._shared`, renders `.tmpl`
  files through Jinja, prepends markers, extends the lock.
  Wired into `agentforge new`.
- `5302bc1` — chunk 3: AGENTS.md.tmpl (~115 lines) + CLAUDE.md
  + .cursorrules. AGENTS.md is the canonical AI-rules document;
  the other two are thin pointers. All three use the three-
  section format.
- `8cf6412` — chunk 4: runbooks 01-05 (set-up, add-tool,
  add-pipeline-task, pick-strategy, write-prompts).
- `f5d4812` — chunk 5: runbooks 06-10 (test, debug, add-memory,
  add-mcp, add-evaluators).
- `7d03021` — chunk 6: runbooks 11-16 + README index (safety,
  observability, multi-provider, deploy, upgrade, config-ref).
- `1cc3fa9` — chunk 7: `agentforge docs` CLI (list / open by
  stem/number/alias / `--check` drift / `--serve` local HTTP).
- (about-to-commit) chunk 8: spec status → shipped + §10
  Implementation Status table + §11 Runbook; features README;
  roadmap; CHANGELOG `[Unreleased]/Added`; state refreshed.

Deviations captured in spec §10:

- Post-Copier injection step rather than Copier primitives —
  Copier lacks clean cross-template `_extra_paths`.
- AGENTS.md `module_list` ships empty for now; auto-population
  is follow-up.
- `--serve` is bare `SimpleHTTPRequestHandler` (no markdown
  rendering).
- CI link-check + TS port deferred.

Tooling notes:
- Jinja2 `autoescape=False` is intentional: markdown / YAML
  output, never HTML in a browser. Bandit B701 + ruff S701
  both noqa'd at the call site.
- `subprocess.run([editor, path])` in `docs <topic>` is
  argv-form with `$EDITOR` from the user's own environment;
  bandit B404/B603 noqa'd.

Ready to push and raise PR #23.

---

## 2026-05-12T06:30 — feat-013 chunk 5 done, PR pending

All five chunks of feat-013 landed on
`feat/013-mcp-integration`:

- `93ba261` — chunk 1: package skeleton + Runner protocols
  + MCPToolDescriptor + MCPToolAdapter + build_adapter.
  Server-name tool prefixing; permissive Pydantic input
  schema from JSON-Schema dict; pyproject entry-point under
  `agentforge.protocols/mcp`.
- `c1099ab` — chunk 2: MCPServerClient (stdio + HTTP + SSE)
  with lazy `mcp` SDK imports. tool_filter + close
  propagation. Three SDK-missing → ModuleError test cases.
- `8b7fb56` — chunk 3: MCPServer exposer with stdio + http
  factories. register_tools using `Tool.input_schema.
  model_json_schema()`. Allowlist semantics (no error on
  unknown).
- `8a48bb0` — chunk 4: MCPBridge orchestrator.
  `from_config(config)` parses `modules.protocols.mcp.config`;
  `start` aggregates tools across clients; serve task
  scheduled; `close` cancels with `_Suppress(CancelledError)`
  and tears down everything.
- (about-to-commit) chunk 5: spec status → shipped + §10
  Implementation Status + §11 Runbook; features README;
  roadmap; CHANGELOG; state refreshed; manifest.yaml shipped
  for `agentforge add module mcp`.

Deviations captured in spec §10:

- Production transport runners (`_SDKClientRunner`,
  `_SDKServerRunner`) scaffolded but `# pragma: no cover` —
  they raise `Production MCP runner not implemented yet`
  until the first live integration test.
- `build_agent_from_config` auto-merging `bridge.tools` is a
  follow-up; today the bridge is opt-in.
- TS port deferred.

Tooling notes:
- mypy override added for `mcp.*` (no py.typed upstream).
- `MCPBridge.from_config` uses `asyncio.get_event_loop().
  run_until_complete` to drive async factories from sync code;
  this is pragmatic now, fully-async resolver hook is v0.3.
- `_Suppress(CancelledError)` is a small CapWords class
  mirroring `contextlib.suppress` (mypy-friendly).

Ready to push and raise PR #24.


## 2026-05-12T11:00 — feat-015 (Pipeline & deterministic tasks) shipped

Branch `feat/015-pipeline-and-tasks` opens PR #25. Full spec in one
PR (framework-only inside the main `agentforge` package; no new
sister packages).

Chunks landed:

- chunk 1 (`255f0f7`): `Task` ABC in
  `agentforge_core.contracts.task` + `PipelineResult` frozen value
  in `agentforge_core.values.pipeline` + `FinishReason` literal
  extended with `"pipeline"` + `run_task_conformance` harness.
- chunk 2 (`ca03e27`): `Pipeline` engine with DAG validation +
  `asyncio.Semaphore` parallelism + per-task
  `asyncio.wait_for` + `on_task_error` continue/fail +
  `PipelineFailure` + `register_task` resolver helper.
- chunk 3 (`69298ca`): `PipelineFindingsTool` built-in tool +
  `Agent(pipeline=...)` kwarg + `Agent.run(task, *, context,
  replay_pipeline)` + system-prompt addendum + budget
  accounting + `__pipeline` recording category +
  `load_pipeline_result` replay + CLI `--replay` integration.
  `Agent.run` refactored under PLR0915 (`_finalize_result` +
  module-level `_tag_run_span`).
- chunk 4 (`9782786`): `modules.pipeline:` schema +
  `PipelineTaskEntry`/`PipelineConfig` +
  `validate_module_configs` extension +
  `build_pipeline_from_config` wired into
  `build_agent_from_config`.
- chunk 5 (`0586e3f`): public re-exports
  (`agentforge.{Pipeline, Task, PipelineResult, PipelineFailure,
  PipelineFindingsTool, register_task}`) +
  `agentforge.testing.run_task_conformance` +
  renderer-compat sanity test.
- chunk 6 (about-to-commit): spec status → shipped + §10
  Implementation Status + §11 Runbook + features README +
  roadmap + CHANGELOG + state refreshed.

Deviations captured in spec §10:

- `Agent.run` gained both `context=` and `replay_pipeline=`
  kwargs (spec showed `context=` only).
- `finish_reason = "pipeline"` is new; CLI maps it to
  generic exit 1 (no separate exit code).
- Mid-run pipeline streaming, end-to-end LLM-using task
  example, and TS port deferred.

Tooling notes:

- Internal `Pipeline` engine collections type findings as
  `list[Any]` (not `list[Finding]`) because the `Finding`
  Protocol declares settable attributes that frozen Pydantic
  finding subclasses don't satisfy structurally under mypy
  strict. The public API (`Task.run` return type,
  `PipelineResult.findings`) stays Finding-typed.
- `_RunState` is a tiny private class threading the engine's
  per-run scratch through `_run_one` / `_record_failure`,
  keeping `Pipeline.run` under PLR0915.

Ready to push and raise PR #25.


## 2026-05-12T14:00 — feat-020 (Chat agents v0.2 scope) shipped

Branch `feat/020-chat-agents-v02` opens PR #26. v0.2 scope only
per the scope-preference exception (one half clearly riskier):
v0.3 postgres / redis / slack drivers + real streaming +
cross-process locking deferred to follow-up PRs.

Chunks landed:

- chunk 1 (`2bd8f38`): `agentforge_core.contracts.chat.{ChatHistoryStore,
  HistoryTruncationStrategy}` ABCs +
  `agentforge_core.values.chat.{ChatTurn, SessionInfo, ChatChunk,
  ChatResponse}` + conformance harnesses.
- chunk 2 (`d6d0a73`): new `agentforge-chat` workspace member with
  `InMemoryChatHistory` + `SqliteChatHistory` drivers + four
  truncation strategies + entry-points + manifest.yaml; root
  pyproject + pre-commit + CI updated.
- chunk 3 (`e4ff78d`): `ChatSession` (send + stream + history +
  reset + close + idempotency + per-turn/per-session budgets +
  guardrails wired); per-session asyncio.Lock registry via
  WeakValueDictionary; LRU+TTL idempotency cache;
  sentence-segmenting `stream()` using buffer-then-stream
  semantics.
- chunk 4 (`200b38e`): new `agentforge-chat-http` workspace
  member with FastAPI REST + WS + SSE + `BearerAuthPolicy` +
  `EnvBearerAuth` + in-process rate limiting + cross-owner 403.
- chunk 5 (`1369c95`): `modules.chat:` config schema +
  `_validate_driver` helper +
  `build_chat_session_from_config` +
  `register_chat_history` / `register_chat_truncation`
  resolver helpers.
- chunk 6 (about-to-commit): spec status → shipped + §11
  Implementation Status + §12 Runbook + features README +
  roadmap + CHANGELOG + state refreshed.

Deviations captured in spec §11:

- Streaming is buffer-then-stream only (strategy ABC has no
  `stream()` method yet).
- Cancellation is pre-LLM only.
- Single-process locking; cross-process Redis lock deferred.
- `BearerAuthPolicy` is a v0.2 placeholder; refactors to
  feat-014's `AuthPolicy` when it lands.
- Approximate token counting in `TokenBudget`.

Tooling notes:

- New filename collision avoided: chat-http's test file is
  `test_chat_server.py` (the workspace already has
  `test_server.py` in agentforge-mcp; pytest collection fails
  on duplicate basenames).
- B008 (`Depends` in defaults) noqa'd on every FastAPI route
  function; standard FastAPI idiom.
- B107 (hardcoded password default) noqa'd on
  `EnvBearerAuth(token_env_var="API_TOKENS")` — the value
  is the env-var NAME, not a token.
- WebSocket consumer extracted to a method (`_consume_stream`)
  so B023 (loop-variable capture in closure) is cleanly
  avoided.
- `uv sync` after adding each package pulls fastapi /
  uvicorn / httpx into the shared venv.

Ready to push and raise PR #26.


## 2026-05-12T16:00 — feat-014 (A2A protocol) shipped

Branch `feat/014-a2a-protocol` opens PR #27. Full-spec scope:
canonical `AuthPolicy` ABC lifted from feat-020's chat-http stub
into `agentforge-core`, plus a new `agentforge-a2a` workspace
member shipping client + server + bridge.

Chunks landed:

- chunk 1 (`76e2373`): `agentforge_core.contracts.auth.AuthPolicy`
  + `Principal` + `A2ACallError` / `A2AAuthError` /
  `A2ATimeout` exceptions + `agentforge.auth.EnvBearerAuth` +
  chat-http `BearerAuthPolicy` aliased to the canonical contract.
- chunk 2 (`b09915b`): new `agentforge-a2a` workspace member;
  `A2AResponse` / `A2APeerConfig` / `A2AEndpointConfig` /
  `A2AExposeConfig` values; `A2AClientRunner` /
  `A2AServerRunner` Protocols with `# pragma: no cover`
  production stubs (mirrors feat-013 MCP); manifest.yaml +
  entry-point.
- chunk 3 (`06f4ba6`): `agent_call` client + `BearerAuth`,
  `MutualTLSAuth`, `build_outgoing_auth` credentials;
  `FakeA2AClientRunner` / `FakeA2AServerRunner` in src/
  for tests + downstream reuse; run_id + budget header
  propagation; 19 unit tests.
- chunk 4 (`4197535`): `A2AServer` FastAPI app with
  `POST /a2a/v1/calls` + `GET /a2a/v1/info`, bearer auth
  via canonical `AuthPolicy`, parent_run_id chain, budget cap;
  `A2ABridge.from_config` orchestrator with start/close
  lifecycle; 15 unit tests (server + bridge).
- chunk 5 (`f925e0b`): `A2AConfig` Pydantic schema +
  `A2ABridge.config_schema = A2AConfig` so feat-012's
  module-schema validator enforces shape; 6 config tests.
- chunk 6 (about-to-commit): spec status → shipped + §10
  Implementation Status + §11 Runbook; features README;
  roadmap; CHANGELOG; state refreshed.

Deviations captured in spec §10:

- Production HTTP runner scoped to `# pragma: no cover`
  until live integration test lands.
- FastAPI used for server (matches chat-http precedent;
  spec §4.4 hinted at Starlette).
- Outgoing auth is dict-driven (no policy abstraction).
- A2A discovery, bi-directional streaming, TS port deferred.

Tooling notes:

- mTLS test fixture uses openssl via subprocess to generate
  a fresh self-signed cert at test time (avoids hardcoded
  PEM blobs that LibreSSL vs OpenSSL parse differently).
- Filename collision avoided: a2a's server test is
  `test_a2a_server.py` (mcp + chat-http already own
  `test_server.py` / `test_chat_server.py`).
- B008 (`Depends` in defaults) noqa'd on every FastAPI
  route function; standard FastAPI idiom.
- B025 caught a duplicate `except TimeoutError` block —
  Python 3.11+ aliases asyncio.TimeoutError to the builtin
  TimeoutError, so a single except clause catches both.

Ready to push and raise PR #27.


## 2026-05-12T18:00 — v0.1.0 release prep

Branch `chore/release-v0.1.0` opens the first tag PR.

- Bumped every workspace package (18 total) from `0.0.0` to
  `0.1.0`.
- Filled `docs/releases/v0.1.0.md` from
  `.claude/templates/release-notes.md` (Codename:
  Foundation).
- CHANGELOG.md renamed `[Unreleased]` → `[0.1.0] —
  2026-05-12` and added fresh empty `[Unreleased]` above.
- Followed `.claude/checklists/pre-release.md` end-to-end.

Pending: PR merge, then `git tag -a v0.1.0` + push + `gh
release create v0.1.0 --notes-file docs/releases/v0.1.0.md`.


## 2026-05-12T19:00 — v0.1.0 tagged + published

`git tag -a v0.1.0` annotated and pushed; `gh release create
v0.1.0 --notes-file docs/releases/v0.1.0.md` published.

Release page:
https://github.com/Scaffoldic/agentforge-py/releases/tag/v0.1.0

First AgentForge release. All 18 workspace packages at 0.1.0.
20 canonical specs (feat-001 through feat-020) shipped. The
v0.2.0 backlog is in docs/roadmap.md "v0.2.0 backlog" section.


## 2026-05-12T20:00 — feat-013 v0.2 production MCP runner

Branch `chore/feat-013-production-mcp-runner` opens the
first v0.2 cycle PR. Four chunks:

- chunk 1 (`eadcf66`): `_SDKClientRunner` real impl —
  `AsyncExitStack`-managed session + transport; `list_tools`
  normalises results to `MCPToolDescriptor`; `call_tool`
  concatenates `TextContent` blocks; `close()` tears
  down. Root pyproject adds `mcp>=1.0,<2` to dev deps.
- chunk 2 (`03bfba9`): `_SDKServerRunner` real impl —
  accumulates registrations; on `serve()` applies SDK
  decorator pattern over registry; stdio transport for
  v0.2; HTTP / SSE expose deferred to v0.2.1.
- chunk 3 (`339753e`): `agentforge-mcp` declares
  `[project.optional-dependencies] mcp = ["mcp>=1.0,<2"]`.
- chunk 4 (`175fdfa`): Live integration test — echo server
  subprocess + `MCPServerClient.from_stdio` round-trip,
  marked `@pytest.mark.live`; default pre-commit / CI gate
  skips via `-m "not live"`. Framework's first live test.
- chunk 5 (about-to-commit): spec §10 v0.2 follow-up
  addendum; troubleshooting table updated; roadmap entry
  flipped; CHANGELOG `[Unreleased] / Added` populated.

Tooling notes:

- The SDK's `@server.list_tools()` / `@server.call_tool()`
  decorators are untyped — each handler gets
  `# type: ignore[untyped-decorator]` on the decorator line
  and `# type: ignore[no-any-unimported]` on the signature
  (return type uses an Any-imported SDK type). The global
  mypy override for `mcp.*` disables follow-imports but
  doesn't suppress these in consumer code.
- Live test runs in 0.45s on developer machine. A dedicated
  "live" CI job lands when feat-014 A2A ships its matching
  production runner (i.e. ≥ 2 live tests justify the job).

Ready to push and raise PR.


## 2026-05-12T22:00 — feat-014 v0.2 production A2A runner + discovery + streaming

Branch `chore/feat-014-production-runner-discovery-streaming`
opens the next v0.2 cycle PR. Closes three v0.1 deferred items
in one bundle. Eight chunks:

- chunk 1 (`149dbac`): `_HTTPXClientRunner` real body wrapping
  `httpx.AsyncClient` (lazy client; HTTP 401/403 → `A2AAuthError`,
  ≥ 400 → `A2ACallError`). `_UvicornServerRunner` real body
  wrapping `uvicorn.Server` (lazy build in `serve()`; `stop()`
  sets `should_exit`). `A2AClientRunner` Protocol gains `get(...)`
  + `post_stream(...) -> AsyncIterator[dict]`. Fake mirrors the
  new surface.
- chunk 2 (`397999e`): Discovery — `A2APeerInfo` +
  `A2AEndpointDescriptor` frozen values. `/a2a/v1/info` returns
  full rich shape with description + JSON-Schema input shapes.
  `discover_peer(peer)` helper + `A2ABridge.discover_all()` +
  `bridge.peer_info` cache. Info URL derived from
  `peer.url.swap("/calls" → "/info")`.
- chunk 3 (`39cdeaf`): Streaming wire format — `A2AChunk` +
  `A2AChunkKind` (step / tool_call / tool_result / done / error).
- chunk 4 (`5aa57bf`): Streaming server `POST /a2a/v1/calls/stream`
  returns SSE `data:` frames. Installs a one-off `on_step` hook
  on the agent; each `Step` → `A2AChunk`. Background `agent.run`
  task pushes terminal `done` / `error` + sentinel. 404 emits a
  single `error` chunk (stream stays "always SSE once
  authenticated").
- chunk 5 (`d633033`): Streaming client `agent_call_stream(...)`
  yields `A2AChunk`. Budget reserve on entry, commit on `done`,
  release in `finally`. Error frames raise A2AAuthError /
  A2ACallError; transport errors funnel through
  `_wrap_stream_errors` helper.
- chunk 6 (`10b0d1b`): Live integration tests (3) under
  `packages/agentforge-a2a/tests/integration/test_a2a_live.py`.
  Each spins up a real `uvicorn.Server` on a random free port +
  real `_HTTPXClientRunner`; round-trips unary / discover /
  stream; tears down. Helpers (deterministic strategy, static
  bearer, `_spawn_server` context manager) live in the test file
  — no extra importable module + no `__init__.py` collision with
  agentforge-mcp's integration dir. Side adjustments:
  `A2AResponse` drops `strict=True` (JSON round-trip
  list↔tuple coercion); pyproject filterwarnings ignores
  `websockets.legacy` / `uvicorn.protocols.websockets`
  DeprecationWarnings.
- chunk 7 (`a810583`): New `live` job in
  `.github/workflows/ci.yml`. Runs `pytest -m live` against
  every package shipping a `tests/integration/test_*_live.py`
  suite (mcp + a2a as of v0.2). Ubuntu + macOS matrix on
  Python 3.13. `continue-on-error: true` — branch protection
  still gates on the main `test` job. Threshold for adding the
  job was ≥ 2 packages with live tests.
- chunk 8 (about-to-commit): spec §10 v0.2 follow-up addendum;
  three new runbook sections (discover, stream, run live);
  roadmap entry flipped to shipped; CHANGELOG `[Unreleased] /
  Added + Changed` populated.

Tooling notes:

- uvicorn's `install_signal_handlers` needs the main thread;
  pytest-asyncio's worker loop may not be on the main thread.
  Live tests no-op the method on the `Server` instance so
  startup proceeds to the socket bind.
- `lifespan="off"` skips FastAPI's lifespan event setup for
  the test server.
- The `_free_port` helper picks a port via a transient
  socket.bind on `127.0.0.1:0`; cross-platform; the small race
  window between close + uvicorn bind has held green on
  developer machine.

Ready to push and raise PR.


## 2026-05-13T00:00 — feat-020 v0.2 follow-up — postgres + redis + slack + per-token streaming + lock + tokeniser

Branch `chore/feat-020-v0.2-followup-postgres-redis-slack-streaming-lock-tokeniser`.
Closes the six v0.1 deferred items in one PR per the user-
chosen "full v0.2 spec" scope. Eight chunks (4+5 combined
since the redis lock lives in the redis chat-history
package).

- chunk 1 (`6f4c258`): `ReasoningStrategy.stream(state)`
  non-abstract default ABC method (backward-compatible:
  default wraps `run()` and yields one terminal `done`).
  New `StreamingEvent` frozen value co-located with
  `ChatChunk`. New `Agent.stream(task)` mirrors
  `Agent.run(task)` setup but drives the strategy via
  `stream()`; final canonical `done` carries the full
  RunResult shape. `ChatSession._stream_impl` graduates
  conditionally on `type(strategy).stream is not
  ReasoningStrategy.stream`; falls back to v0.1 buffer-
  then-stream otherwise.
- chunk 2 (`952c024`): Provider-aware tokeniser —
  `tiktoken_tokeniser` + `anthropic_tokeniser` with lazy
  SDK imports + `ModuleError` remediation. `TokenBudget`
  accepts optional `tokeniser:` kwarg; falls back to the
  4-chars-per-token heuristic when None.
- chunk 3 (`ee99648`): `agentforge-chat-history-postgres`
  sister package. asyncpg-backed `ChatHistoryStore` with
  dual-table schema + composite index + `CREATE TABLE IF
  NOT EXISTS` bootstrap. `PostgresRunner` Protocol +
  `_AsyncpgPoolRunner` under `# pragma: no cover`.
  `PostgresFakeRunner` in src/_inmem_runner.py for unit
  tests. 100% coverage on the new package via
  `run_chat_history_conformance` + branch tests.
- chunk 4+5 (`76f7896`): `agentforge-chat-history-redis`
  sister package + cross-process `SessionLock`. Redis key
  layout: turn hash + per-session sorted set + session
  meta hash + index set. Native TTL via `EXPIRE`.
  `RedisSessionLock` uses `SET NX PX` + UUID fencing + Lua
  unlock. `agentforge_chat._locks` extended: `SessionLock`
  Protocol + `SessionLockFactory` alias +
  `InMemorySessionLock` wrapping the v0.1 asyncio.Lock +
  `default_session_lock_factory`. `ChatSession.__init__`
  accepts optional `session_lock_factory`. Bonus fix in
  `_stream_per_token`: don't break on agent.stream's `done`
  — continue so the generator drains naturally and
  `Agent.stream`'s `finally: reset_run(token)` fires
  deterministically.
- chunk 6 (`7e5f19a`): `agentforge-chat-slack` reference
  channel adapter. One `ChatSession` per Slack channel.
  Maps `message` + `app_mention` events to `session.send`;
  batched `chat.update` every `batch_window_s` seconds
  (Slack rate-limits per channel; per-token impractical).
  Tests use distinct channel IDs to dodge the shared
  asyncio.Lock-across-event-loops issue in
  `_LockRegistry`. Live test scaffold omitted (no free CI
  Slack workspace).
- chunk 7 (`1617e9a`): `live` CI job extended with
  Postgres + Redis services + env-gated tests.
  `RUN_LIVE_POSTGRES_DSN` + `REDIS_URL` set on Ubuntu;
  macOS leaves them unset so service-backed tests skip
  cleanly.
- chunk 8 (about-to-commit): spec §11 v0.2 follow-up table
  + §12 runbook (5 new sections: postgres, redis, multi-
  worker, tokeniser, slack), roadmap flipped to shipped,
  CHANGELOG `[Unreleased] / Added + Changed` populated.

Tooling notes:

- `dict.setdefault(k, factory())` evaluates the default
  eagerly even when the key exists — Slack adapter switched
  to explicit get-or-create.
- pytest-asyncio mode=auto + function-scoped loops mean
  shared module-level `asyncio.Lock` objects (via
  `_LockRegistry`) outlive their loops, causing hangs in
  cross-test reuse of the same session_id. Workaround for
  now is distinct session_ids per test; a v0.3 cleanup
  would lazily create the lock at __aenter__ time.

Ready to push and raise PR.

---

## 2026-05-13 — feat-014 v0.3 follow-up shipped

Closed the two remaining v0.2-deferred items in a single PR
per user-chosen "Full v0.3 bundle" scope: per-token A2A
streaming + chunk-kind unification. The per-run hook kwarg
on `Agent.run` was **obviated** by the streaming refactor
(no caller remaining) and dropped from scope, not deferred.

Chunks (each gated through `uv run pre-commit run
--all-files` before commit):

- chunk 1 (`a3ed2d7`): `StreamingChunkKind = Literal[text,
  thinking, step, tool_call, tool_result, done, error]`
  in `agentforge_core.values.chat`; `ChatChunkKind` and
  `A2AChunkKind` aliased to it. `step` kept in the union
  for strategies that want step-level granularity. Tests
  assert `typing.get_args` shape and that A2AChunk accepts
  the newly-unified kinds.
- chunk 2 (`09674b5`): `A2AServer._stream_call` rewritten
  to drive `Agent.stream(task)`. Drops
  `_STEP_KIND_TO_CHUNK_KIND`, `_chunk_kind_for`, the
  `asyncio.Queue` + backgrounded `_run_agent` coroutine,
  and the `agent._on_step.append/remove` dance. Strategy's
  terminal `done` is swallowed; server emits its own
  canonical `done` with `output` + `cost_usd` + `run_id`.
  Tests now exercise a `stream()`-overriding
  `_PerTokenStrategy` (text × 3 + done) plus a
  `_SilentStrategy` (default stream → one canonical done).
- chunk 3 (`b3724a4`): live integration test
  `_PerTokenStrategy` overrides `stream()` to yield three
  `text` tokens + a `tool_call` + a `tool_result` + a
  terminal `done`. `test_stream_round_trip` asserts the
  canonical chunk sequence end-to-end against a real
  uvicorn server + `_HTTPXClientRunner`. All three live
  tests pass locally.
- chunk 4 (about-to-commit): spec §10 v0.3 follow-up
  subsection + per-chunk table + deviations (`step_hook=`
  kwarg obviated; v0.2 step-level shape requires opt-in
  override; `step` kind preserved); §11 runbook refresh
  with per-token usage + a "How do I expose per-token
  streaming on my strategy?" snippet; roadmap flipped;
  CHANGELOG `[Unreleased] / Added + Changed` populated.

Tooling notes:

- `AgentState` has no `output` field — `Agent._extract_output`
  picks the last non-system step's content. Stream-overriding
  strategies must `state.steps.append(Step(...))` before the
  terminal `done` so the canonical chunk carries the assembled
  output.
- `Agent.stream` already swallows the strategy's terminal
  `done` and emits its own with the full RunResult shape; A2A
  server mirrors that, swallowing the strategy's done a second
  time and emitting the canonical wire frame.
- Plain `X = Y` aliases preferred over `X: TypeAlias = Y`
  (ruff UP040 wants `type X = Y`, but PEP 695's
  `TypeAliasType` doesn't compose well with Pydantic literal
  validation — plain assignment threads the literal through).

---

## 2026-05-13 — feat-009 v0.2 vendor backends shipped

Closed the four vendor backends spec §4.4 left for v0.2 in
one PR per user-chosen "All four backends in one PR" scope.
Each package implements the existing StepHook + FinishHook
contract via __call__ dispatch (mirroring OpenTelemetryHook)
plus the runner-Protocol pattern from feat-020 v0.2 (Protocol
+ production runner under # pragma: no cover + in-memory fake
in src/).

Chunks (each gated through `uv run pre-commit run
--all-files` before commit):

- chunk 1 (`45ea58a`): agentforge-statsd. Counters
  (<prefix>.step.<kind>, tool.<name>, run.finish.<reason>),
  timings (step + run duration_ms), gauges (run cost +
  tokens). FakeStatsdRunner records every call as a tagged
  tuple. SDK is the [statsd] extra.
- chunk 2 (`4e089c5`): agentforge-langfuse. One trace per
  run (keyed by current_run().run_id), one span per step,
  nested span on tool_call, scores for cost_usd +
  duration_ms on finish, flush(). Zero-step runs get a
  synthetic trace at finish so the score has a home. SDK is
  [langfuse]. Steps fired outside a RunContext are dropped
  silently (RuntimeError, not LookupError — caught
  explicitly).
- chunk 3 (`d616ca3`): agentforge-phoenix. log_step /
  log_tool_call / log_run events on a project namespace.
  Same redaction shape as OTel. SDK is [phoenix].
- chunk 4 (`ef8fbcf`): agentforge-evidently. Buffers per-
  step rows keyed by run_id, appends a __run__ row on
  finish, asks the runner to build an Evidently Report from
  pandas.DataFrame, writes to <report_dir>/<run_id>.json.
  Falls back to a plain JSON dump if the SDK errors. SDK is
  [evidently]; pandas pulled transitively.
- chunk 5: workspace registration done in-line with each
  package (root pyproject deps + uv.sources + testpaths +
  coverage.source + mypy overrides; ci.yml + .pre-commit
  mypy/bandit/pytest unit lists). Consistency pass-through
  on this chunk found nothing to fix.
- chunk 6 (about-to-commit): feat-009 spec §10 v0.2 follow-
  up subsection + per-chunk table + deviations (no live CI
  for vendor backends; Phoenix uses SDK events not OTel
  exporter; Evidently is end-of-run; per-run hook kwarg not
  needed); Runbook gets four new sections; roadmap flipped
  to shipped; CHANGELOG `[Unreleased] / Added` entries +
  four new entry-points listed.

Tooling notes:

- `current_run()` raises **RuntimeError** (not LookupError)
  when no RunContext is bound — three of the four hooks
  (langfuse/phoenix/evidently) needed to catch RuntimeError
  specifically and silently drop steps fired outside a run.
  Statsd doesn't need this because its metrics don't depend
  on run_id correlation.
- ModuleError lives at `agentforge_core.production.exceptions`
  (not `.errors` — caught that on the first commit).
- ruff UP040 auto-fixes some test-file constants
  (e.g. `# noqa: S108`) under hook auto-fix; second commit
  attempt succeeds after the fix lands.
- Production from_config classmethods + their _build_*_runner
  factories live under `# pragma: no cover` since they need
  the live SDK; live tests cover them when env vars set.

---

## 2026-05-13 — feat-021 Reranker shipped

Promoted the Reranker sub-feat from the un-numbered backlog
(feat-005 follow-up) to canonical feat-021. One PR per
user-chosen "ABC + SentenceTransformers default + Retriever
integration" scope.

Chunks (each gated through `uv run pre-commit run
--all-files` before commit):

- chunk 1 (`0118b4f`): canonical
  docs/features/feat-021-reranker.md spec following the
  feat-020 template (Metadata + Why + framework + benefits +
  Specifications + Plug-and-play + Cross-language + Tests +
  Risks + Out-of-scope + References + Implementation
  status (filled in chunk 5) + Runbook (filled in chunk 5)).
  Added a new "Retrieval" subsection to features/README.md
  for the row; flipped the roadmap sub-feat-backlog entry to
  a cross-reference.
- chunk 2 (`6c5a198`): Reranker ABC at
  agentforge_core.contracts.reranker — async rerank /
  close / capabilities / supports. Conformance suite
  run_reranker_conformance with 9 invariants (empty input,
  top_k<1 raises, top_k=None returns all, top_k truncates,
  scores in [0,1], descending sort, id/text/metadata
  non-mutation, input immutability, unknown capability).
  Two reference impls (IdentityReranker, ReverseReranker)
  in tests pass it.
- chunk 3 (`6edf080`): Retriever.__init__ gains optional
  reranker + over_fetch_factor kwargs (default factor=3 per
  Cohere/Voyage best practice). retrieve(query, top_k=K)
  pulls K * factor from the store + reranks to K when set,
  plain slicing otherwise. close() propagates. Constructor
  validates over_fetch_factor >= 1. .reranker property
  exposes the injected instance.
- chunk 4 (`fbe6d50`): agentforge-reranker-
  sentence-transformers workspace member. Wraps
  sentence_transformers.CrossEncoder.predict; applies a
  numerically-stable sigmoid to the raw logits so scores
  satisfy VectorMatch.score in [0, 1]. Runner-Protocol
  pattern (CrossEncoderRunner Protocol +
  _SentenceTransformersRunner under pragma: no cover +
  FakeCrossEncoderRunner in src/_inmem_runner.py with
  set_scores test knob). Entry-point
  agentforge.rerankers:sentence-transformers. SDK is the
  optional [sentence-transformers] extra. Conformance suite
  passes via test_conformance_suite.
- chunk 5 (about-to-commit): spec §11 Implementation
  status (per-chunk table + deviations including the
  obviated YAML resolver wiring) + §12 Runbook (4 sections:
  add reranking, write a custom Reranker, tune
  over_fetch_factor, run live test); roadmap row flipped
  to shipped; CHANGELOG [Unreleased] Added entry + Changed
  note on Retriever signature; state.

Tooling notes:

- First feature with the spec-first workflow (Branch number
  must match a canonical feat-NNN spec; the first commit on
  the branch lands the spec to satisfy that rule). Chunk 1
  is docs-only and gates clean.
- VectorMatch.score is constrained to [0, 1] by Pydantic;
  the raw cross-encoder logits (range roughly -10..+10)
  must be normalised. Standard practice is sigmoid; we
  ship a numerically-stable variant in
  agentforge_reranker_sentence_transformers.reranker
  (_sigmoid).
- Live test gated on RUN_LIVE_RERANKER=1 — the model
  download (~80MB) is a CI footgun if always-on.
- ruff PLR2004 (magic numbers) fires on test assertions
  like `len(results) == 2` — auto-fixed across two
  pre-commit runs.

---

## 2026-05-14 — feat-021 v0.2 follow-up shipped

Closed the deferred config-driven wiring deviation from
feat-021's initial PR. Per user-chosen "Full retrieval:
block + Retriever builder" scope.

Chunks (each gated through `uv run pre-commit run
--all-files` before commit):

- chunk 1 (`307e1e5`): RetrievalConfig + RerankerEntry
  Pydantic models in agentforge_core.config.schema. New
  AgentForgeConfig.retrieval: RetrievalConfig | None field.
  _validate_retrieval helper in module_schemas.py walks
  the block, resolves vector_store under "vector_stores",
  embedder under "embeddings", reranker under "rerankers"
  — all three categories already existed as entry-point
  groups (no new groups invented). Legacy modules.retriever
  block kept valid with a deprecation notice on the
  docstring. Tests cover schema round-trip, default values,
  knob lower-bound validation, extra-field rejection.
- chunk 2 (`178358f`): build_retriever_from_config in
  cli/_build.py. Resolves all three sub-components, checks
  each against the expected ABC (VectorStore /
  EmbeddingClient / Reranker), threads top_k /
  over_fetch_factor / batch_size into Retriever.__init__.
  _instantiate() updated to prefer from_config(**cfg)
  keyword expansion so SentenceTransformersReranker's
  from_config(*, model=...) signature works; falls back to
  dict-positional then cls(**cfg). Five unit tests covering
  None-return, build-without-reranker, build-with-reranker
  + over_fetch_factor threading, unregistered driver
  raises, wrong-ABC raises.
- chunk 3 (`79ac9a4`): end-to-end YAML smoke test at
  tests/integration/test_retrieval_yaml.py. Writes a YAML
  fixture to tmp_path, loads through load_config, builds
  the retriever, indexes 6 docs, retrieves with top_k=2,
  asserts the reranker was invoked once with the 6-element
  over-fetch pool (2 * 3 = 6) and the final result is
  truncated to 2.
- chunk 4: CLI sanity check passed without code changes.
  `agentforge config validate --path test-retrieval.yaml`
  returns "OK"; `agentforge config schema` surfaces
  RetrievalConfig + RerankerEntry in the JSON Schema
  output. The CLI is polymorphic on the schema; nothing
  to update.
- chunk 5 (about-to-commit): feat-021 spec §11 + §12 — flipped
  the deferred "No retrieval.reranker: YAML resolver
  wiring" deviation to shipped; new v0.2 follow-up
  subsection with per-chunk table + two v0.2-follow-up
  deviations (Agent.__init__(retriever=...) deferred,
  modules.retriever legacy block kept). New §12 Runbook
  entry "How do I wire a Retriever from agentforge.yaml?"
  with a complete YAML + load+build snippet + validation
  command. Roadmap entry extended. CHANGELOG
  [Unreleased]/Added entry + Changed notes on _instantiate
  behaviour + modules.retriever deprecation.

Tooling notes:

- `_instantiate(cls, cfg)` previously called from_config
  with a single dict-positional arg. Vendor packages
  (sentence-transformers, langfuse, phoenix, evidently,
  statsd) all ship keyword-only from_config signatures,
  so the dict-positional shape never worked for them
  through the resolver. Existing _instantiate callers
  (memory/evaluators/pipeline/tools modules) don't ship
  from_config at all — they fall through to cls(**cfg).
  So the keyword-expansion change is backward-compatible
  in the in-tree tree; externally-shipped modules using
  the legacy dict-positional shape still load via the
  TypeError-fallback branch.
- The Resolver.register signature is positional
  (`register(category, name, cls)`), not keyword-only.
  Ruff's PT006 fires on `@pytest.mark.parametrize` when
  the names string isn't a tuple; switch to
  `("field", "bad_value")` form.

---

## 2026-05-14 — feat-021 vendor reranker sister packages shipped

Closed the "Vendor reranker sister packages" open item from
feat-021's initial PR. Three managed-API rerankers bundled
into one PR per user-chosen scope. All follow the
sentence-transformers package template (Runner Protocol +
production wrapper under pragma: no cover + in-memory fake
in src/).

Chunks (each gated through `uv run pre-commit run
--all-files` before commit):

- chunk 1 (`ca1371a`): agentforge-reranker-cohere. Wraps
  cohere.Client.rerank(query, documents, model, top_n).
  Default model rerank-english-v3.0. Capabilities {managed,
  batched}. 9 unit tests + conformance suite.
- chunk 2 (`f244861`): agentforge-reranker-voyage. Wraps
  voyageai.Client.rerank(query, documents, model, top_k).
  Voyage names the response-cap arg `top_k`, not Cohere's
  `top_n`; the runner Protocol surfaces this as a
  per-vendor parameter name. Default model rerank-2.
- chunk 3 (`096c074`): agentforge-reranker-mixedbread.
  Wraps MixedbreadAI.rerank(model, query, input, top_k).
  Mixedbread names the document list `input` (not
  `documents`) — runner Protocol normalises. Default model
  mixedbread-ai/mxbai-rerank-large-v1.
- chunk 4: workspace sweep done inline per package; no
  new integration test (existing test_retrieval_yaml.py
  already exercises the YAML resolver path with a fake
  reranker — adding per-vendor variants would duplicate).
- chunk 5 (about-to-commit): feat-021 spec §11 vendor
  follow-up subsection + per-chunk table; flipped the
  "Vendor reranker sister packages" open item to shipped.
  §12 Runbook gets a new "How do I swap rerankers without
  code changes?" section with one YAML snippet per vendor
  + pip install commands. Roadmap entry extended. CHANGELOG
  [Unreleased]/Added gets one entry per package + a note
  on the three new entry-points.

Tooling notes:

- Each vendor SDK names its parameters differently
  (Cohere: top_n, documents; Voyage: top_k, documents;
  Mixedbread: top_k, input). The runner Protocol pattern
  isolates the caller from these inconsistencies — each
  package's runner Protocol surfaces the vendor's
  parameter shape, but the reranker class always calls
  rerank() with a consistent (query, candidates, top_k)
  interface.
- Score-normalisation: all three vendors return scores
  already in [0, 1], so no sigmoid is needed (unlike
  sentence-transformers which returns raw logits). Each
  package applies a defensive max(0, min(1, score)) clamp
  for safety against edge cases.
- Ruff PLR2004 (magic-number-comparison) fires on test
  assertions like `len(results) == 2`. Auto-fixed with
  `# noqa: PLR2004` on first pre-commit pass.

---

## 2026-05-14 — feat-002 + feat-009 v0.3 polish + feat-021 follow-up bundle shipped

Big bundled PR closing the three remaining v0.2 cycle items
in one go per user-chosen "Full bundle as described" scope.

Chunks (each gated through `uv run pre-commit run
--all-files` before commit):

- chunk 1 (`d096b80`): ReActLoop.stream() per-iteration
  override. Mirrors run()'s loop structure but yields a
  `step` StreamingEvent each time state.steps is appended.
  Terminal `done` event (carrying run_id + cost_usd) is
  swallowed by Agent.stream which emits its own canonical
  done with full RunResult shape.
- chunk 2 (`ebf7af3`): child OTel spans. Single-point
  instrumentation in StrategyBase._call_llm (llm.call span)
  + StrategyBase._dispatch_tool (tool.<name> span) covers
  every strategy. strategy.iteration spans added to
  ReActLoop (run + stream) and PlanExecuteLoop;
  ToT + MultiAgent deferred (their nested loop structure
  needs extract-method refactor). evaluator.<name> span
  added to Agent._run_evaluators. End-to-end test asserts
  full span tree via InMemorySpanExporter.
- chunk 3 (`d8419c1`): A2A W3C TraceContext propagation.
  Client _build_headers calls TraceContextTextMapPropagator
  .inject(headers) after existing run-id / budget headers.
  Server _handle_call + _stream_call extract the
  traceparent and open an `a2a.call` span with the extracted
  context as parent. Streaming path uses manual
  __enter__/__exit__ because async generators don't compose
  with `with` blocks. 3 unit tests cover injection
  (with/without span) + cross-process trace_id stitching.
- chunk 4 (`e347c35`): content-based PII redaction +
  Agent retriever wiring. OpenTelemetryHook gains
  redact_value_patterns kwarg; patterns compile once, scan
  stringified values after the key-based pass.
  build_agent_from_config now calls
  build_retriever_from_config and threads the result into
  Agent(retriever=...). The kwarg + RuntimeContext storage
  were already wired in feat-021 — only the builder hook
  was missing.
- chunk 5 (about-to-commit): docs across three specs
  (feat-002 §"Implementation status" gets a v0.3 polish
  subsection, feat-009 §11 flips three deferred items to
  shipped, feat-021 §11 flips the
  Agent(retriever=...) deviation), CHANGELOG entry,
  state files.

Tooling notes:

- `with tracer.start_as_current_span(...):` requires the
  body of the wrapped loop to be indented one level deeper.
  For ToT's nested loop structure (depth × parents ×
  candidates) this would mean cascading indent shifts of
  ~50 lines; deferred to a v0.3.x patch that does the
  extract-method refactor properly.
- `async generator + context manager` don't compose cleanly
  (`with`-block exit fires before the generator is
  exhausted on the caller side). For `_stream_call` in the
  a2a server, we use manual `__enter__()` / `__exit__()`
  to keep the span open across yields.
- ruff PT006 (parametrize names must be tuple) fires on
  the comma-separated string form. Use the tuple form
  `("field", "bad_value")` instead.
- ruff RUF012 fires on `class _NoAuth: headers: dict = {}`
  — mutable default at class level. Move to `__init__`.

---

## 2026-05-14T11:00 — feat-002 + feat-009 v0.3.x strategy follow-ups bundle in review

Closes the two deferred items from PR #40 in one bundled
PR per the user's "Strategy follow-ups bundle" choice:

1. `strategy.iteration` OTel spans on TreeOfThoughts +
   MultiAgentSupervisor (the two deferred at the end of
   PR #40 — their loop bodies were too large for an
   in-place `with`-block addition).
2. `stream()` overrides on PlanExecuteLoop, TreeOfThoughts,
   and MultiAgentSupervisor — closes the feat-002 v0.3+
   follow-up that was deferred case-by-case at the spec
   level.

Branch: `chore/feat-002-feat-009-strategy-streams-iteration-spans`.

Chunked across 6 commits:

- chunk 1 (`57e66ce`): lift `_events_for_new_steps` from
  `react.py` into `strategies/_base.py` so the three
  follow-up strategies' `stream()` overrides can reuse it.
- chunk 2 (`9f7ca68`): ToT `strategy.iteration` via
  extract-method. New `_iterate_depth(state, by_id,
  survivors, current_depth) -> list[_Node]` holds the
  inner depth-iteration body; `run()` (and later
  `stream()`) wrap the helper call in
  `tracer.start_as_current_span("strategy.iteration", ...)`.
  Extended `agentforge-otel/tests/unit/test_hook.py`
  asserts the span tree.
- chunk 3 (`5890b8a`): MultiAgent `strategy.iteration` via
  extract-method. New `_iterate_round(state, runtime,
  round_idx, prior_results) -> tuple[list[_WorkerResult],
  bool]` holds the round body; the bool flags both
  "no valid assignments" and "every worker errored" exits.
  Same span pattern; extended test asserts.
- chunk 4 (`3b654cf`): PlanExecuteLoop.stream() override.
  Mirrors `run()` but yields `_events_for_new_steps` after
  each phase: plan-build (which records `think` + `plan`),
  `_execute_plan` (batched think-only or tool steps —
  yields after the helper returns since `asyncio.gather`
  packs the batch), then synthesize.
- chunk 5 (`87b9d9a`): ToT.stream() override. Mirrors
  `run()` but yields `_events_for_new_steps` after each
  `_iterate_depth` call (flushing all branch steps for
  that depth) and again after synthesize.
- chunk 6 (about-to-commit): MultiAgentSupervisor.stream()
  override + docs (feat-002 + feat-009 specs) + roadmap
  cleanup (flips three v0.3+ items that PR #40 actually
  shipped to ~shipped~) + CHANGELOG entry + state files.

Tooling notes:

- Confirmed the PlanExecute step-kind sequence: each
  think-only step records `act` (via
  `_call_llm(kind="act")` inside `_run_step`) followed by
  an explicit `observe` record. The supervisor delegation
  call records `plan` not `think` (via
  `_call_llm(kind="plan")` in `_delegate`). MultiAgent's
  stream emits `[plan, delegate × N, synthesize, done]`
  per round-then-aggregate path.
- Extract-method refactors keep the `with` block clean —
  preferable to in-place indent shifts on 30+ line bodies.

---

## 2026-05-14T12:00 — feat-022 BM25 + vector hybrid search in review

Closes one of the three un-numbered v0.2 retrieval sub-feats
per the user's "Full spec in one PR" scope choice.

Branch: `feat/022-hybrid-search`.

Chunked across 5 commits:

- chunk 1 (`e42dbbc`): canonical spec at
  `docs/features/feat-022-hybrid-search.md` + catalogue
  row + roadmap pointer (strikes the un-numbered Hybrid
  Search bullet).
- chunk 2 (`588c532`):
  `VectorStore.lexical_search` default-method on the ABC
  (raises `NotImplementedError` by default; drivers that
  declare `"hybrid_search"` MUST override). Pure-Python
  `_BM25Index` helper at `agentforge_core/_bm25.py` with
  Robertson defaults (k1=1.5, b=0.75). InMemoryVectorStore
  declares `"hybrid_search"` and ships a native lexical
  impl backed by a lazy `_BM25Index` rebuilt on demand
  after any `upsert`/`delete`. `run_hybrid_search_conformance`
  opt-in suite added to `agentforge-core` and re-exported
  through `agentforge.testing`. Unit tests for _BM25Index +
  InMemoryVectorStore hybrid path.
- chunk 3 (`f5af6c1`): `Retriever.mode` +
  `Retriever.rrf_k` constructor kwargs. Constructor
  validates the store declares `"hybrid_search"` when
  `mode="hybrid"`. New private `_rrf_fuse(vec, lex, *,
  limit)` implementing Reciprocal Rank Fusion (Cormack
  2009 default k=60). `retrieve()` dispatches to
  `_retrieve_hybrid` when `mode="hybrid"` —
  `asyncio.gather` of `store.search()` and
  `store.lexical_search()`, then RRF, then optional
  reranker post-fusion. Tests cover constructor
  validation, fused ordering, top_k truncation, vector
  mode regression, post-fusion reranker.
- chunk 4 (`b2917dd`): RetrievalConfig gains `mode` +
  `rrf_k`. `build_retriever_from_config` forwards both.
  Integration test asserts the YAML round-trips end-to-end
  and the resulting Retriever fuses both paths.
- chunk 5 (about-to-commit): spec implementation-status
  flip to shipped + catalogue row flip + roadmap pointer
  flip + CHANGELOG entry + state files.

Design notes:

- Picked `Literal["vector", "hybrid"]` on a single
  `Retriever` class rather than a separate
  `HybridRetriever`. The mode flag keeps the build path
  simpler and avoids two near-duplicate constructors.
- BM25 lives as a *private* `_bm25.py` module (single
  class + helper) — not part of the public API yet.
  Drivers consume it as an implementation detail; the
  public surface is `VectorStore.lexical_search`.
- RRF fuses by **rank**, sidestepping the score
  calibration problem entirely. Locked v0.2; future v0.3+
  may add weighted-score fusion behind a config knob.
- Conformance suite is *opt-in* (`run_hybrid_search_conformance`,
  not `run_vector_conformance`). Existing drivers that
  don't declare `"hybrid_search"` keep passing the main
  suite unchanged.

---

## 2026-05-14T13:00 — feat-022 v0.2 follow-up: native hybrid for Postgres + SQLite in review

Closes the two sister-package deferrals from feat-022
(PR #42) in one bundled PR per the user's "Native hybrid
for Postgres + SQLite" choice.

Branch: `feat/022-hybrid-postgres-sqlite-native`.

Chunked across 3 commits:

- chunk 1 (`69a450e`): Postgres native lexical_search.
  `init_schema()` is now idempotent and adds an
  `embedding_tsv tsvector` generated column (`ALTER TABLE
  ... ADD COLUMN IF NOT EXISTS`) over
  `to_tsvector('english', coalesce(text, ''))` + a GIN
  index on `embedding_tsv`. New `_LEXICAL_SEARCH_SQL`
  uses a CTE wrapping `ts_rank_cd(embedding_tsv,
  plainto_tsquery('english', $1))` with metadata JSONB
  containment, then max-normalises in a window function so
  the driver returns scores in `[0, 1]` per match. The
  `hybrid_search` capability joins `native_ann` post-init
  (same gating pattern); calling `lexical_search` before
  `init_schema()` raises a clear RuntimeError. The unit
  test fake runner gains a `plainto_tsquery` branch that
  uses the framework's `_BM25Index` so unit tests get
  directionally identical ordering without spinning up
  Postgres. Live tests gain `run_hybrid_search_conformance`
  under existing `RUN_LIVE_POSTGRES` gating.
- chunk 2 (`55c5a38`): SQLite native lexical_search via
  FTS5. `_SCHEMA_SQL` extended with a `vectors_fts` FTS5
  virtual table over `vectors.text` (`unicode61`
  tokeniser) + three triggers
  (`AFTER INSERT/UPDATE/DELETE ON vectors`) that keep the
  FTS index in sync without application code having to
  write to the FTS table directly. `lexical_search` runs
  a JOIN between `vectors_fts` and `vectors` ordered by
  `-bm25(vectors_fts) DESC`, with max-normalisation in
  Python. User input goes through `_escape_fts_query`
  which wraps every term in double-quotes so FTS5 syntax
  (`AND`/`OR`/`*`/parens/colons) stays literal.
  `hybrid_search` always declared (schema is provisioned
  in `from_path()`).
- chunk 3 (about-to-commit): feat-022 spec gains a
  "v0.2 follow-up: native Postgres + SQLite lexical
  paths" subsection with per-chunk table + deviations
  list. Catalogue row + roadmap pointer extended. CHANGELOG
  entry. State files updated.

Tooling notes:

- aiosqlite's `fetchall()` returns `Iterable[Row]`; mypy
  --strict rejects indexing. Wrap in `list(...)` to
  materialise.
- ruff PLR0911 ("too many return statements") fires on
  `PostgresFakeRunner._dispatch_execute` once the
  `ALTER TABLE ... ADD COLUMN ... embedding_tsv` early
  return is added. Tagged `# noqa: PLR0911` — the
  function is essentially a switch over SQL prefixes and
  splitting it would obfuscate the simple dispatch logic.
- Postgres `embedding_tsv tsvector GENERATED ALWAYS AS
  (...) STORED` requires Postgres 12+. We don't gate on
  the version explicitly; the pgvector dependency already
  implies a modern Postgres.

---

## 2026-05-14T14:00 — feat-023 GraphRAG hybrid retrieval in review

Closes the second of the three un-numbered v0.2 retrieval
sub-feats per the user's "GraphRAG hybrid retrieval
(feat-023)" + "Full spec in one PR" choice.

Branch: `feat/023-graphrag-hybrid-retrieval`.

Chunked across 4 commits:

- chunk 1 (`5192abf`): canonical spec at
  `docs/features/feat-023-graphrag-hybrid.md` + catalogue
  row + roadmap pointer (strikes the un-numbered GraphRAG
  bullet).
- chunk 2 (`5f4ce61`): `GraphExpansion` value at
  `agentforge_core/values/retrieval.py` — frozen, strict,
  `arbitrary_types_allowed=True` for the `GraphStore`
  field. `Retriever.__init__` gains `graph_expansion:
  GraphExpansion | None = None`. `retrieve()` refactored
  into a unified pipeline `(base retrieve) → (graph
  expand) → (rerank)`; `_retrieve_hybrid` split into
  `_retrieve_vector_candidates` + `_retrieve_hybrid_
  candidates` so rerank happens once at the end of the
  pipeline. New `_expand_via_graph` runs
  `store.traverse()` per seed via `asyncio.gather`,
  synthesises `VectorMatch`es per neighbour with score =
  `seed.score * decay**depth` and metadata
  `agentforge.expanded_from` + `agentforge.hop`, dedup by
  id with direct hits winning. Without a reranker the
  expanded list is returned whole (seeds at the head,
  neighbours appended); with a reranker the augmented set
  is narrowed to top_k. Unit tests cover validation,
  single/multi-hop, edge-type filter, score decay, dedup,
  missing-graph-node tolerance, reranker post-expansion,
  hybrid composition.
- chunk 3 (`d588e1b`): `RetrievalConfig.graph_expansion`
  + `GraphExpansionConfig` block. Builder resolves graph
  store under the `graph_stores` resolver category,
  converts `edge_types` (YAML list → list[str]) to tuple
  at the boundary before constructing the frozen
  `GraphExpansion`. Integration test registers an
  `_IntegrationGraphStore` and exercises a YAML with
  `graph_expansion: { max_hops: 2, edge_types: [CITES] }`.
- chunk 4 (about-to-commit): spec implementation-status
  flip + catalogue + roadmap flips + CHANGELOG + state.

Design notes:

- Composition, not new class. Graph expansion is a
  decorator over the existing `Retriever.retrieve()`
  pipeline — same `Retriever` class with three orthogonal
  axes: (vector / hybrid), (reranker yes/no), (graph
  expansion yes/no).
- Id alignment between vector and graph stores is a
  caller contract. Misalignment silently skips expansion
  for that seed (logged at DEBUG). Fail-loud was rejected
  because mixed corpora (some docs only in vectors, some
  only in graph) are common in practice.
- Without a reranker, `top_k` is treated as the minimum
  *direct-hit* count, not a hard cap on the final result.
  Users who want a hard cap configure a reranker.
- YAML lists don't coerce to tuple under
  `ConfigDict(strict=True)`. Pattern: schema uses
  `list[str]`, value type uses `tuple[str, ...]`, builder
  converts.

---

## 2026-05-14T15:00 — feat-024 schema migrations framework in review

Closes the last un-numbered v0.2 persistence sub-feat
per the user's "Schema migrations framework" +
"Spec + framework + all four drivers" choices.

Branch: `feat/024-schema-migrations`.

Chunked across 7 commits:

- chunk 1 (`126cb67`): canonical spec at
  `docs/features/feat-024-schema-migrations.md` +
  catalogue row + roadmap pointer.
- chunk 2 (`3ac96b1`): agentforge-core framework —
  `Migration` value (4-digit id + name + up body +
  SHA-256 checksum) + `MigrationStatus` + `Migrator`
  runtime Protocol + `MigrationChecksumError` (subclass
  of ModuleError) + `discover_migrations(path, *,
  suffix)` helper at `agentforge_core/migrations/`.
  Re-exported through `agentforge_core` top-level.
  18 unit tests.
- chunk 3 (`e501788`): Postgres — `PostgresMigrator` +
  2 SQL files. The vectors table stays under the
  dim-parameterized `init_schema()` because
  `vector(N)` can't be in a static migration file.
  Fake runner extended; live integration test added.
- chunk 4 (`f537d1c`): SQLite — `SqliteMigrator` + 3
  SQL files (`0000_migrations_table`,
  `0001_initial` claims + vectors + vector_meta,
  `0002_fts5` feat-022 delta). `from_path` now
  bootstraps through the migrator. Renamed both
  packages' migrator tests to unique basenames
  (`test_postgres_migrator.py` /
  `test_sqlite_migrator.py`) to avoid pytest
  collection collisions on `test_migrator`.
- chunk 5 (`0784244`): Neo4j — `Neo4jMigrator` + 2
  Cypher files. `_split_statements` strips `//`
  comments + blank lines + splits on `;` to honour
  Neo4j 5.x's one-statement-per-`run()` rule. Applied
  migrations tracked as `:AgentforgeMigration` nodes.
- chunk 6 (`8e169cf`): SurrealDB — `SurrealMigrator`
  + 2 SurrealQL files. SurrealDB v1.x lacks
  multi-statement transactions — operators
  single-flight migrate calls. Applied migrations
  tracked in `agentforge_migrations` SurrealDB table.
- chunk 7 (about-to-commit): CLI extension —
  `agentforge db migrate` routes through
  `memory.migrator()` when present (falls back to
  legacy `init_schema()` otherwise). New
  `agentforge db migrate-status` lists per-migration
  applied + checksum-match status. Spec status flip,
  catalogue, roadmap, CHANGELOG, state.

Scope reductions:

- The vector tables on Postgres + SurrealDB stay
  under their existing dim-parameterized
  `init_schema()` because the migration framework
  treats migration bodies as static text. Parameterized
  migrations land in v0.3+.
- `down` migrations / schema rollback deferred to v0.3.

Tooling notes:

- Pydantic v2 fires `string_too_short` before custom
  validators; relaxed `Migration.id`'s
  `Field(min_length=...)` to 1 and rely on the custom
  validator's `4 digits` message.
- mypy --strict on the Postgres migrator needed
  `_fetch_applied` to return `dict[str, dict[str,
  Any]]` (was `object`) so the call sites can read
  `["applied_at"]` as `datetime`.
- pytest collection conflicts on `test_migrator.py`
  across two packages — rename one (we renamed both:
  `test_postgres_migrator.py` + `test_sqlite_migrator.py`).

---

## 2026-05-14T16:00 — feat-024 v0.3 polish (parameterized migrations) in review

Closes the dim-parameterized item deferred from PR #45
per the user's "Parameterized migrations (feat-024
v0.3+)" + "Full bundle: core + Postgres + SurrealDB"
choices.

Branch: `feat/024-parameterized-migrations-vectors`.

Chunked across 3 commits:

- chunk 1 (`ce3141a`): `render_migration_up(body,
  variables)` at `agentforge_core/migrations/template.py`.
  Uses `string.Template.safe_substitute` so unknown
  placeholders pass through. Re-exported via
  `agentforge_core.migrations`. 6 new unit tests
  including a checksum-over-template invariant test.
- chunk 2 (`a25193a`): all four per-driver migrators
  gain `variables=` kwarg. Postgres + SurrealDB get
  per-store migration subdirectories: vector migrations
  move to `migrations/vector/0100_vectors.{sql,surql}`
  (id range 0100+ avoids colliding with memory's 0001
  in the shared tracking table).
  `Postgres/SurrealVectorStore.migrator()` returns a
  migrator configured with `variables={"dimensions":
  str(self._dim)}` + the vector subdir path.
  `_build_init_schema_sql` / `_build_init_schema`
  helpers removed; both vector stores' `init_schema()`
  delegate to the migration framework.
- chunk 3 (about-to-commit): spec subsection + roadmap
  flip + CHANGELOG + state.

Design notes:

- Per-store subdirectories use `path.glob(pattern)`
  which is non-recursive, so the memory store's
  migrator at `migrations/` doesn't pick up files in
  `migrations/vector/`. Same for SurrealDB.
- The `0000_migrations_table.{sql,surql}` is duplicated
  in both the root and the vector subdir (identical
  content). Same SHA-256 checksum, so the second store
  to run sees `0000` already applied and skips. The
  shared tracking table works for both stores.
- ID ranges per store (Postgres + SurrealDB): memory =
  0001-0099, vector = 0100-0199, graph = 0200-0299
  (future). Future stores follow the same pattern to
  keep ids unique across the shared tracking table.
- SQLite + Neo4j get the `variables=` kwarg as
  passthrough — no functional change today, but
  unblocks future driver-specific parameterized
  migrations without another framework bump.
- Checksum-over-template is the load-bearing decision:
  re-deploying with a different dim value produces the
  same checksum, so drift detection stays correct.
  Verified with a dedicated unit test in chunk 1.

---

## 2026-05-14T17:00 — feat-025 (Neo4jVectorStore + SurrealDB native lexical_search) in review

Closes two adjacent retrieval-completeness gaps per the
user's "Both in one PR" scope choice. After merging,
every shipped VectorStore (InMemory / Postgres / SQLite /
SurrealDB / Neo4j) passes both `run_vector_conformance`
and `run_hybrid_search_conformance`.

Branch:
`feat/025-neo4j-vector-store-plus-surrealdb-lexical`.

Chunked across 3 commits (chunks 2-4 bundled):

- chunk 1 (`8bfb6a3`): canonical spec at
  `docs/features/feat-025-neo4j-vector-store.md` +
  catalogue + roadmap.
- chunks 2-4 (`465b7bd`):
  - `Neo4jVectorStore` at
    `agentforge_memory_neo4j.vector` with vector +
    fulltext + delete + capability gating. Uses
    `AfVector` label (coexists with `AfNode` +
    `Claim`). Cypher queries:
    `db.index.vector.queryNodes` /
    `db.index.fulltext.queryNodes`. Lucene fulltext
    scores max-normalised to `[0, 1]` client-side
    (mirrors SQLite + SurrealDB).
  - Migration files at `migrations/vector/0100_vectors.cypher`
    with `${dimensions}` template (feat-024 v0.3
    helper) + constraint + vector + fulltext index.
  - `Neo4jVectorStore.migrator()` /
    `init_schema()` plumbing.
  - Entry-point registration:
    `[project.entry-points."agentforge.vector_stores"]
     neo4j = ...`.
  - `VectorFakeRunner` in tests/unit/conftest.py
    delegates to `InMemoryVectorStore` for vector
    upsert/search/delete + `_BM25Index` for the
    fulltext path. Recognises tracking-table reads/
    writes for `:AgentforgeMigration`.
  - 7 Neo4j unit tests including both conformance
    suites.
  - SurrealDB `migrations/vector/0101_fts.surql`:
    `DEFINE ANALYZER af_vector_en TOKENIZERS class
    FILTERS lowercase, ascii;` +
    `DEFINE INDEX af_vector_fts ON af_vector FIELDS
    text SEARCH ANALYZER af_vector_en BM25;`.
  - `SurrealVectorStore.lexical_search` via
    `WHERE text @0@ $query` +
    `search::score(0) AS raw` + max-normalisation.
  - `SurrealVectorStore.capabilities()` now declares
    `{"native_ann", "hybrid_search"}` after
    `init_schema()`.
  - SurrealFakeRunner gains a `_dispatch_vector_fts`
    branch routing the FTS predicate to `_BM25Index`
    over the in-memory vectors backing.
  - 2 new SurrealDB unit tests.
- chunk 5 (about-to-commit): spec status flip,
  catalogue + roadmap flips, CHANGELOG, state.

Design notes:

- Decided NOT to ship a brand-new conformance fake for
  Neo4j; the `VectorFakeRunner` delegates to the
  existing in-memory implementations. Saves ~200 lines
  of bespoke cosine + BM25 code in the test fixture.
- Bundled chunks 2-4 in one commit because they share
  the same `VectorFakeRunner` / SurrealFakeRunner
  extensions, and splitting would require interleaved
  test-fixture changes that wouldn't pass pre-commit
  in isolation.
- The Postgres + SurrealDB pattern of per-store
  migration subdirs (`migrations/vector/`) applies
  cleanly to Neo4j too. No restructure of the existing
  Neo4j memory + graph migration dirs needed —
  vector lives at a new subdir.
- The Neo4j `VectorFakeRunner` reads
  `InMemoryVectorStore._items` directly (private
  attribute). Acceptable for a test fixture since the
  fake is co-located with the package; production
  code never touches `_items`.

---

## 2026-05-14T18:00 — feat-020 v0.3 polish (sentence-window streaming output guardrails) in review

Closes the deferred safety gap from feat-020 v0.2 per
the user's "Sentence-window streaming guardrails" pick.

Branch: `chore/feat-020-sentence-window-guardrails`.

Chunked across 2 commits:

- chunk 1: `_SentenceWindowBuffer` at
  `agentforge_chat/_window.py` (push + flush;
  punctuation-then-whitespace OR newline OR 200-char
  hard cap boundary heuristic). `ChatSessionConfig.safety_mode`
  Literal expanded to add `"sentence-window"`. `SafetyMode`
  type alias re-exported from `agentforge_chat`.
  `ChatSession.__init__` gains
  `safety_mode: SafetyMode = "buffer-then-stream"`.
  `_stream_per_token` dispatches: in sentence-window
  mode every `text` event accumulates in the buffer;
  each completed sentence runs through
  `_agent._guardrails.check_output(sentence, ctx)`
  before being emitted as a `ChatChunk(kind="text")`.
  Non-text events pass through unbuffered. End-of-stream
  flushes residual through the same validator. Terminal
  `check_output` is skipped in sentence-window mode
  since each sentence was already validated.
  `build_chat_session_from_config` reads
  `chat_cfg.session.safety_mode` and forwards into
  `ChatSession(safety_mode=...)`. 7 buffer unit tests +
  4 session-level safety-mode tests; 48 existing chat
  tests pass without regression.
- chunk 2 (about-to-commit): feat-020 spec §11 flips
  the "post-stream guardrails" deviation + "sentence-
  window streaming guardrails" deferred item to
  shipped; adds a "v0.3 polish" subsection describing
  the pipeline. Roadmap line flipped. CHANGELOG entry
  for the new safety_mode value + the additive
  Literal change. State files updated.

Design notes:

- `stream-then-redact` is kept as an accepted Literal
  value but aliases sentence-window for v0.3. A future
  v0.3+ pass may implement true inline regex redaction
  without buffering — the schema field stays valid so
  YAMLs can opt into the (eventually distinct)
  behaviour without a config-schema bump later.
- The terminal `check_output` is intentionally skipped
  in sentence-window mode: each sentence was already
  validated, and re-running over the validated
  cumulative could trigger surprising results for
  non-idempotent validators.
- Per-token `text` events in sentence-window mode
  don't emit `ChatChunk` until a sentence boundary
  fires. This is the intended latency trade-off.

---

## 2026-05-14T17:00 — PR #49 opened: v0.2.0 cut (bundled)

User pivoted from per-chunk PR sequence to one bundled PR
for the entire v0.2 cut after merging PR #48
(feat-020 v0.3 polish). Four commits on
`chore/v0.2-trackers-alignment`:

- **a185a84** chore: align trackers ahead of v0.2.0 cut.
  Roadmap fixes + v0.3 backlog section + feat-003 catalogue
  reclassification.
- **f01e9e0** feat(feat-003): ship 5 first-party LLM provider
  sister packages (agentforge-anthropic, -openai, -voyage,
  -litellm, -ollama). 7036 line insertion across 66 files.
- **926ccdf** docs(feat-019): add 5 v0.2 runbooks (17–21) +
  provider-table polish in runbook 13 + AGENTS.md.tmpl rows.
- **40d498e** chore(release): cut v0.2.0 — coordinated bump
  across all 34 workspace members + CHANGELOG flip
  ([Unreleased] → [0.2.0] — 2026-05-14) + roadmap "Tagged
  releases" table.

PR URL: https://github.com/Scaffoldic/agentforge-py/pull/49

Pattern decisions worth remembering:

- Provider sister packages use `model_id=` constructor kwarg
  (not `model=`) so the Agent resolver's
  `cls(model_id=model_id)` call works. `runner=None` lazy-builds
  the production SDK runner so `Agent(model="anthropic:...")`
  works out-of-the-box.
- New test files inside packages MUST use unique basenames
  per package (`test_anthropic_client.py`, not `test_client.py`)
  to avoid pytest's `ImportPathMismatchError` when no
  `__init__.py` is present in tests/ dirs. Existing packages
  with `__init__.py` everywhere (bedrock) take a different
  path — don't mix the two.
- `OllamaEmbeddingClient` requires explicit `dimensions=`
  on construction; Ollama doesn't expose model→dim via
  the API (unlike OpenAI/Voyage where it's in a known
  table). Callers must know the model's dim ahead of time.
- LiteLLM wrapper conservatively declares only
  `{tools}` capabilities since underlying-provider
  capabilities vary; users wanting caching / thinking /
  streaming should use the matching native sister package.

## 2026-05-15T07:48 — Split CI into per-OS workflows (PR #49)

Replaced single `.github/workflows/ci.yml` (Linux + macOS +
Windows matrix on every PR) with three files:

- `ci-linux.yml` — lint-and-type, test, live-ubuntu,
  coverage-ratchet. Triggers: `pull_request` + `push: main`.
  This is the per-PR gate.
- `ci-windows.yml` — Windows test job. Trigger:
  `workflow_dispatch` only. Run manually before a release
  or when touching path / subprocess / filesystem code.
- `ci-mac.yml` — macOS test + live-macos jobs. Trigger:
  `workflow_dispatch` only.

Rationale: cuts ~⅔ of per-PR CI minutes. AgentForge is
pure Python with no native extensions, so macOS/Windows
catch a narrow set of regressions (path separators, line
endings, subprocess) that don't change on every PR.

Branch-protection follow-up needed post-merge: required
status checks pointed at the old workflow's `test
(ubuntu-latest, …)` job name will need to be updated to
the new `Test (Linux, Python 3.13)` name. Documented in
the PR description.

`.pre-commit-config.yaml`, `AGENTS.md`, and
`scripts/README.md` references to `ci.yml` updated.

## 2026-05-15T08:30 — Copilot scaffold + README + v0.2.0 release notes (PR #49)

Three threads bundled into PR #49:

1. **GitHub Copilot scaffold support.** New
   `packages/agentforge/src/agentforge/templates/_shared/.github/copilot-instructions.md`
   is a one-line pointer to `AGENTS.md`, mirroring the
   existing `CLAUDE.md` and `.cursorrules` pointer files.
   The Copier post-render hook
   (`_shared_scaffold.inject_shared_scaffold`) picks it up
   via `rglob("*")` automatically — no code change needed in
   the scaffold injector. Updated `_shared_scaffold.py`
   docstring + `new_cmd.py` comment to mention the new file.
   Added regression test
   `test_new_cmd.py::test_scaffold_ships_ai_assistant_instructions`
   asserting every AI-assistant pointer file lands in a
   scaffolded agent.

2. **README rewrite.** Old README was stuck at the v0.0
   pre-alpha narrative (feat-001 only, Bedrock-only).
   Rewritten to lead with the AI-assisted-development story:
   scaffolded agents ship framework-aware instructions for
   Claude Code / Cursor / Copilot / Aider / Codex /
   Windsurf, plus 21 runbooks. The developer focuses on
   requirements + design; the AI follows runbooks +
   invariants; `agentforge upgrade` keeps instructions
   fresh. Capability table reflects all 34 v0.2 packages.

3. **v0.2.0 release notes.** Filled the
   `.claude/templates/release-notes.md` skeleton at
   `docs/releases/v0.2.0.md`. Mirrors the v0.1.0 file
   structure: Highlights → What's new → Breaking changes
   (None) → Migration guide → Coordinated release train
   (34-row package table) → Cross-language status →
   Install/upgrade → Shipped features → Acknowledgements →
   Full changelog → v0.3.0 backlog. This becomes the body
   of the GitHub Release when the v0.2.0 tag is cut
   post-merge.

CHANGELOG.md [0.2.0] section gained a Copilot bullet under
Added.

## 2026-05-15T09:00 — v0.2.0 released

PR #49 merged via `70d79c3` ("Merge pull request #49 from
Scaffoldic/chore/v0.2-trackers-alignment"). CI on the merge
commit ran on the new `ci-linux.yml` workflow and finished
green (run 25897552058).

Tag + release cut on a clean local main:

- `git tag -a v0.2.0 -m "AgentForge v0.2.0 — Drivers"`
- `git push origin v0.2.0`
- `gh release create v0.2.0 --title "v0.2.0 — Drivers"
  --notes-file docs/releases/v0.2.0.md`

Release URL: https://github.com/Scaffoldic/agentforge-py/releases/tag/v0.2.0

34 workspace packages now at `0.2.0`. 16 new sister packages
introduced in the v0.2 cycle (5 LLM providers + 4 rerankers
+ 4 observability backends + chat-history-postgres / -redis
/ -slack). `.claude/state/current.md` reset to idle; next
pick comes from the v0.3 backlog.

Open follow-ups recorded as `flags_for_user` in
current.md:

1. Branch protection on `main` still references old job
   name `Test (ubuntu-latest, Python 3.13)`. Update required
   status checks to `Test (Linux, Python 3.13)` from the
   split CI workflows.
2. PyPI publish for the 16 new packages — `uv build` +
   `twine upload`, or wait for CI publish automation.

## 2026-05-15T11:30 — v0.2.1 rename + Trusted Publishing in flight

Branch `feat/v0.2.1-rename-and-trusted-publishing` (off PR
#50's branch) prepares the **first PyPI-publishable** AgentForge
release. v0.2.0 stays git-only — the bare name `agentforge` on
PyPI is owned by an unrelated project (`DataBassGit/AgentForge`
v0.6.5).

Changes:

- **Distribution rename `agentforge` → `agentforge-py`** in
  `packages/agentforge/pyproject.toml` `[project] name`.
  Python import path `from agentforge import Agent` is
  unchanged — `[tool.hatch.build.targets.wheel] packages =
  ["src/agentforge"]` keeps the import name. Mirrors the
  `python-dateutil` (installs as `python-dateutil`, imports as
  `dateutil`) pattern.
- **Cross-package deps pinned to `~= 0.2.1`** across all 34
  workspace `pyproject.toml` files. Built wheel metadata
  verified to carry `Requires-Dist: agentforge-core~=0.2.1`
  etc. Honours ADR-0015 once published.
- **Root `pyproject.toml`** updated — `[tool.uv.sources]`
  and the workspace `dependencies` switched to
  `agentforge-py`. Pulled the squatted `agentforge==0.6.5`
  out of `uv.lock` resolution (was previously sneaking in
  via the workspace dep).
- **Sister packages depending on the runtime**
  (`agentforge-chat`, `agentforge-chat-http`, `agentforge-a2a`,
  `agentforge-testing`) switched dep string to `agentforge-py`.
- **All 34 `__version__` constants bumped to `0.2.1`.**
- **Scaffolded agent pyproject templates** (`minimal`,
  `code-reviewer`, `patch-bot`, `docs-qa`, `triage`,
  `research`) switched their runtime dep to `agentforge-py`.
- **`.github/workflows/release.yml` shipped.** Trusted
  Publishing pipeline: `build` builds 68 artefacts (34
  wheels + 34 sdists) via `uv build --all`, uploads to
  `dist/` GitHub artefact; `publish` job is gated on the
  `pypi` GitHub environment and uses
  `pypa/gh-action-pypi-publish@release/v1` with PyPI OIDC.
  `skip-existing: true` so partial-failure re-runs are safe.
- **`docs/releases/v0.2.1.md` shipped** as the release notes
  body for the GitHub Release.
- **`CHANGELOG.md`** flipped `[Unreleased]` → `[0.2.1] —
  2026-05-15` with the rename + pin + Trusted Publishing
  bullets. v0.2.0 stays as a separate section above.
- **`playbooks/publish-to-pypi.md` updated** — blocker §0
  marked RESOLVED, owner identity is `scaffoldic`, and §0a
  lists the 34 PyPI Project Names for pending-publisher
  registration (33 still to add; `agentforge-py` already
  done by user).
- **`docs/roadmap.md`** Tagged releases table gains the v0.2.1
  row.

Pre-commit gate green. `uv build --all` produces 68 clean
artefacts including `agentforge_py-0.2.1-py3-none-any.whl`.
Smoke verified: `from agentforge import Agent` imports
correctly post-rename.

**User action items before this PR's tag triggers the
publish:**

1. Add 33 more pending publishers on PyPI (list in
   `playbooks/publish-to-pypi.md` §0a). Same Owner /
   Repository / Workflow / Environment values; only the PyPI
   Project Name field varies.
2. Create the `pypi` GitHub environment with self as required
   reviewer (Settings → Environments → New environment).
3. Update branch protection on `main` to reference the new
   `Test (Linux, Python 3.13)` job name (carried over from
   v0.2.0 follow-up).
4. After this PR + PR #50 merge, on clean main:
   `git tag -a v0.2.1 -m "AgentForge v0.2.1 — Publishable"
   && git push origin v0.2.1`. The tag push triggers
   `release.yml`; approve the `pypi` environment when
   prompted; PyPI uploads 34 packages.

---

## 2026-05-21T13:42 — v0.2.3 shipped (bug-007 upgrade-flow fix)

Three coordinated releases shipped today (v0.2.1 was tagged
2026-05-20 with 4 packages live; today brought v0.2.2 + v0.2.3
plus 4 more packages to the live set, total 8 of 34).

**Bugs found + fixed via scaffold-and-upgrade validation:**

- bug-001…006 (PR #53, v0.2.2) — scaffold path bugs. `agentforge
  new` produced an agent that couldn't run end-to-end: provider
  package not in deps, `agent.strategy` missing, no console
  script, `.env` not loaded, stale error strings,
  distribution-name drift in install hints.
- bug-007 (PR #55, v0.2.3) — upgrade path bugs.
  `agentforge new` didn't persist
  `.agentforge-state/answers.yml`; `agentforge upgrade`
  delegated to Copier's VCS-required `run_update`. Fixed both:
  `new_cmd` writes answers ourselves, `upgrade_cmd` uses
  `run_copy` against a temp dir + per-managed-file copy.

**v0.2.3 sign-off state:**

- 8 packages live on PyPI: `agentforge-core`, `-py`,
  `-anthropic`, `-bedrock`, `-chat`, `-a2a`, `-memory-sqlite`,
  `-testing`. Each upgraded via manual `uvx twine upload` for
  v0.2.2 and v0.2.3 (existing-project version uploads — no
  new-project quota).
- 26 packages still pending. `release.yml` workflow fired on
  v0.2.3 tag push but 429'd on the first new-project creation
  (`agentforge-chat-history-postgres`). Daily quota window
  already exhausted; tomorrow opens fresh. Path forward:
  `gh workflow run release.yml --ref v0.2.3` daily.
- v0.2.3 GitHub Release page live at
  <https://github.com/Scaffoldic/agentforge-py/releases/tag/v0.2.3>.
- v0.2.2 git tag exists **locally only** (intentional —
  v0.2.3 supersedes it; pushing it would trigger a redundant
  `release.yml` run that re-burns the daily quota window).
- bug-008 filed for v0.2.4 (cosmetic — `_template_version`
  always renders `0.0.0+unknown` because
  `importlib.metadata.version()` looks up the import name
  instead of the PyPI distribution name).

**Pipeline rule update:** `.claude/checklists/pre-release.md`
§9 + `feedback_workflow` memory rule 9 now flag tag + GitHub
Release as **non-skippable even when PyPI publishing is
partial.** v0.2.2 was shipped without a tag (we skipped it
to avoid burning the daily quota); recovery required
back-dating the tag locally and surfacing the lesson here.
`release.yml` is idempotent (`skip-existing: true`), so the
fear was misplaced.

**Files / commits / PRs:**

- PR #53 — `chore/validate-via-code-reviewer-scaffold` — bugs
  001-006 + regression test.
- PR #54 — `chore/v0.2.2-release` — 34-package version bump,
  CHANGELOG, `docs/releases/v0.2.2.md`.
- PR #55 — `chore/v0.2.3-fix-bug-007-upgrade` — bug-007 fix +
  three new regression tests + 34-package version bump,
  CHANGELOG, `docs/releases/v0.2.3.md`.
- PR #56 (open) — bug-008 doc + `pre-release.md §9` tag
  callout. Doc-only.
- 7 bug docs landed under `docs/bugs/`.
- Two memory updates: `project_v02_cut_in_flight.md` (full
  sign-off snapshot), `feedback_workflow.md` (tag-skip rule).

---

## 2026-05-27T22:00 — bug-009 + bug-010 fix landed on a single branch (PR pending)

A downstream consumer surfaced two related defects in v0.2.3
during a Generative-UI integration design review. Both shipped
together on
`fix/bug-009-react-loop-drops-tool-calls` because they're two
halves of the same problem — `tool_calls` must round-trip both
in-flight (LLM history within a run) and across runs (chat
history persisted to disk).

**bug-009 — P0 — ReAct dropped `response.tool_calls`; Bedrock
Converse rejected every tool-using prompt on iteration 2.**
Root cause was a three-point interaction: `Message` had no
`tool_calls` field, `ReActLoop.run`/`stream` discarded
`response.tool_calls` when re-feeding assistant turns, and each
provider's `_message_to_<provider>` translated messages in
isolation (no native tool-use blocks on assistant turns).
OpenAI and Anthropic-direct had the same latent shape; all three
fixed.

**bug-010 — P2 (arguably P1 functionally) —
`ChatSession._persist_assistant` only wrote the final assistant
text; intermediate `act` / `observe` steps stayed on
`result.steps` and never reached `ChatHistoryStore`.** Generative-
UI clients couldn't render tool activity, AND the next chat
turn's prompt (built from `history.load()` in `_compose_task`)
lost prior tool context entirely. Fixed via new
`ChatSessionConfig.persist_steps: bool = True` knob + new
`_persist_steps_from_result` / `_persist_steps_from_events`
helpers covering both `.send()` and `.stream()`. `ChatResponse.tool_calls`
(previously hardcoded `()`) populated from aggregated act-step
calls. `StreamingEvent.metadata["tool_call"]` enriched additively
so chat session can persist tool turns from the stream path
without reaching into `AgentState`.

**Branch state:**

- 6 commits, all green through full pre-commit gate
  (ruff/mypy --strict/bandit/pytest/coverage ≥ 90).
  - `294ab12` core `Message.tool_calls` + ReActLoop populate + tests
  - `23be0e0` bedrock/openai/anthropic providers + per-provider tests
  - `638700a` bug-009 doc → fixed, new bug-011 follow-up, CHANGELOG
  - `a53d68d` workspace bump 0.2.3 → 0.2.4 (34 pyprojects + uv.lock)
  - `74e02eb` bug-010 impl (schema, session.py, build.py, _base.py)
  - `f25b7f8` bug-010 tests + doc → fixed + CHANGELOG amend
- Branch pushed to origin; tracking set.
- **PR NOT opened.** Title suggestion:
  *"fix: round-trip tool_calls end-to-end (bug-009 + bug-010)"*.
  URL: <https://github.com/Scaffoldic/agentforge-py/pull/new/fix/bug-009-react-loop-drops-tool-calls>.
- Test count growth: 1318 → 1332 (+14 regression tests).

**Files in flight at end-of-session:**

- `docs/bugs/bug-009-react-loop-drops-tool-calls-bedrock-validation.md` — committed; status fixed in 0.2.4.
- `docs/bugs/bug-010-chatsession-drops-tool-steps.md` — committed; status fixed in 0.2.4. (Was previously untracked WIP from earlier the same day; folded into this PR.)
- `docs/bugs/bug-011-provider-conformance-harness.md` — committed; open; v0.3 backlog.
- `docs/bugs/bug-012-*.md` through `docs/bugs/bug-020-*.md` — 9 NEW untracked bug docs filed by the user in parallel during this session. Not reviewed or committed; user WIP. The originally-colliding `bug-011-runtime-doesnt-wire-mcp-bridge.md` was self-resolved by the user moving its content to `bug-020-runtime-doesnt-wire-mcp-bridge.md`.

**v0.2.4 release queue (when this PR merges):**

- All 34 `packages/*/pyproject.toml` already at `0.2.4`.
- `uv.lock` regenerated.
- `CHANGELOG.md` `[0.2.4]` entry covers bug-009 + bug-010 +
  bug-011 (filed).
- Two unrelated v0.2.4-queued items (no scope on this branch):
  - **bug-008** — `_template_version()` looks up wrong dist name. ~5-line fix. Will need its own commit (or fold into a chore PR) before tagging v0.2.4.
  - PR #56 — bug-008 doc + checklist callout — already merged into main (came across in today's `git pull --ff-only`, was on `docs/v0.2.3-followups-bug-008-tag-rule` branch which is no longer the current branch).

**PyPI publish state (unchanged today):** 32 of 34 live at
v0.2.3. `agentforge-phoenix` + `agentforge-statsd` remain;
final drip-publish window 2026-05-28 ≈ 11:05 UTC. See
`PYPI_PUBLISH_TRACKER.md` at workspace root. **v0.2.4 publish
will be a coordinated 34-package upload AFTER the two stragglers
land at 0.2.3, OR may be released as the first 34-at-once cut if
admin@pypi.org has lifted the quota by then.**

**Next session pick-up:**

1. Triage the 9 new untracked bug docs (bug-012 through bug-020) the
   user filed in parallel during this session. Decide which need
   v0.2.4 fixes and commit the doc files (probably in a separate
   `docs:` PR from the current branch).
2. Open the PR for `fix/bug-009-react-loop-drops-tool-calls`.
3. Decide whether to fold bug-008 into the same PR or its own.
4. Finish the v0.2.3 drip-publish (2 packages) so v0.2.4 has a clean baseline.

## 2026-06-02T11:30 — v0.2.4 MCP cluster: triage shipped, runtime wiring opened

PyPI v0.2.3 drip COMPLETE (34/34 live — phoenix + statsd landed
2026-05-28).

Triaged the 9 untracked bug docs against real source via 3 parallel
verification agents (corrected several as-filed claims), added a
"Framework-level vs derived-agent-level" section to each, reclassified
bug-016 → enh-001 (HTTP transport = feature gap, not a defect). Also
added that triage to the workspace doc templates (bug/enhancement/README).

PRs:
- **#57** docs/triage (bug-012…020 + enh-001) — MERGED.
- **#58** fix bug-009/010 (tool_calls round-trip) — MERGED. main now at 0.2.4.
- **#59** fix bug-020 (P0, runtime never wired modules.protocols) +
  bug-014 (P1, from_config crashed inside a running loop) — OPEN.
  2 commits (`9282000`, `25a43bb`), full gate green. Consume path only;
  server-side `expose` rejected (stdio-hijack guard) — deferred with
  enh-001. New `ProtocolBridge` core contract; `Agent(protocol_bridges=)`;
  `build_protocols_from_config` wired into `build_agent_from_config`
  (also fixed latent zero-caller `build_tools_from_config` gap).

**Paused 2026-06-02, resuming evening IST.** Remaining v0.2.4 cluster
(each its own branch off main): bug-012 → bug-017 → bug-015 → bug-019 →
bug-018 → bug-013 → enh-001, plus bug-008 (~5 lines). Tag v0.2.4 only
after the cluster lands (CHANGELOG header is `[0.2.4] — unreleased`).
PyPI post-drip chores: revoke ~/.pypirc token, Trusted Publishing,
delete PYPI_PUBLISH_TRACKER.md.

## 2026-06-03T00:00 — v0.2.4 cluster: PR #59 merged, bug-012 opened (#60)
PR #59 (bug-020 + bug-014, MCP runtime wiring) merged to main (c2f1132) —
the cluster unblocker. Synced main, deleted the merged branch.
Started bug-012 on `fix/bug-012-mcp-adapter-separator`: MCP tool-name
separator `.`→`__` so Bedrock/OpenAI/Anthropic tool-name charset
(`^[a-zA-Z0-9_-]{1,64}$`) accepts MCP tools. adapter.py + tests (incl.
charset regression test) + feat-013 spec + agentforge-mcp README +
CHANGELOG; bug-012 doc → fixed in 0.2.4. Full gate green (87df76a).
PR #60 open. Next: bug-017 → bug-015 → bug-019 → bug-018 → bug-013 →
enh-001; bug-008 before tag; then tag v0.2.4.

## 2026-06-03T01:30 — v0.2.4 cluster: bug-012 merged (#60), bug-017 opened (#61)
PR #60 (bug-012, MCP `.`→`__` separator) merged to main (3cf2bdc). Its CI
Live job first failed — env-gated `test_mcp_live.py` still asserted
`echo.echo`; local pre-commit skips live tests, so the rename slipped past.
Fixed in 0bc8386. LESSON: any MCP adapter/client/bridge naming change must
be checked against packages/agentforge-mcp/tests/integration (live job only).
Started bug-017 on `fix/bug-017-tool-name-validator`: validate tool-name
charset `^[a-zA-Z0-9_-]{1,64}$` at all 3 provider request-build boundaries.
Design decision (user asked "best approach at framework level"): shared
`validate_tool_name` + `ToolNameInvalidError(ProviderError)` in core, invoked
per-provider; core `ToolSpec` deliberately NOT auto-validated (neutral
representation, charset is a per-provider wire constraint that merely
coincides today). Docs: feat-003/004/013, @tool docstring, scaffold
02-add-a-tool runbook. Full gate + Live CI green (3131f92). PR #61 open.
Next: bug-015 → bug-019 → bug-018 → bug-013 → enh-001; bug-008 before tag.

## 2026-06-03T02:30 — v0.2.4 cluster: bug-017 merged (#61), bug-015 opened (#62)
PR #61 (bug-017, tool-name charset validator) merged to main (077795a).
Started bug-015 on `fix/bug-015-meta-extra-chain`. The reported bug
(`agentforge-py[mcp]` doesn't pull the mcp SDK) was the tip — a full audit
of all 34 packages' pyproject deps+extras found EVERY vendor SDK is an
optional extra (the meta comment claiming ollama/litellm hard-bundle was
wrong). Fixed 3 defect classes in agentforge/pyproject.toml (extras + [all]):
12 missing chains (ollama/litellm/voyage/mcp/langfuse/phoenix/statsd/
evidently/reranker-{cohere,voyage,mixedbread,sentence-transformers}); 1
phantom extra (bedrock[bedrock] → bare, SDK is hard dep); 1
eager-import-as-optional (agentforge-chat imports aiosqlite at package
import but declared it optional → made hard dep like memory-sqlite, dropped
[sqlite] extra, updated README+manifest). mcp ModuleError text (4 sites) →
agentforge-mcp[mcp]. New generic test_extras_chain.py parses every sister
pyproject and asserts each meta extra chains exactly the leaf's extras
(catches missing + phantom for future packages too). Full gate + Live CI
green (9622d7e). PR #62 open. Next: bug-019 → bug-018 → bug-013 → enh-001;
bug-008 before tag.

## 2026-06-03T03:30 — v0.2.4 cluster: bug-015 merged (#62), bug-019 opened (#63)
PR #62 (bug-015 meta extra-chain) merged to main (c166ecd). Note: its
first Live CI run failed on a transient `docker pull postgres:16` Docker
Hub timeout (infra, not code) — `gh run rerun --failed` cleared it. The CI
Live job depends on pulling postgres:16 at runtime; flaky on registry
hiccups (harden later via digest pin / retry if it recurs).
Started bug-019 on `fix/bug-019-entry-string-normalise`. Scope wider than
the reported string-form symptom: the single-key-mapping sugar
(`- geval: {rubric}`, in the schema's own example YAML) was equally broken
under strict+forbid. Fix: shared `_normalise_named_entry` + a
`model_validator(mode="before")` on BOTH EvaluatorEntry and GuardrailEntry
(one validator per type covers evaluators + guardrails input/output/
tool_gates; composes through Pydantic list validation under strict). All
three shapes (string / single-key mapping / canonical) load. Flipped the
old feat-012 "string shorthand NYI" test to a positive load_config test;
updated feat-012 Implementation status. Full gate + Live CI green
(f12a2d4). PR #63 open. Next: bug-018 → bug-013 → enh-001; bug-008 before
tag, then cut v0.2.4.

## 2026-06-03T04:30 — v0.2.4 cluster: bug-019 merged (#63), bug-018 opened (#64)
PR #63 (bug-019 config sugar) merged to main (b153199). Started bug-018 on
`fix/bug-018-chat-session-create` — P0: POST /sessions 500'd on fresh
SQLite (ChatServer sets metadata before turn 1; driver inserted the row
only lazily on append). Audit widened scope: Postgres AND Redis raise
identically; in-memory never raised but hid metadata-only sessions from
list_sessions. Fix landed both bug-doc options: (1) update_session_metadata
upserts in sqlite/postgres/redis (INSERT...ON CONFLICT DO NOTHING /
hset-if-absent; existing last_active_at untouched), in-memory lists
metadata-only sessions; (2) ChatHistoryStore.create_session() added as a
CONCRETE (non-abstract) ABC method — additive to the locked ABC per
ADR-0007, so third-party drivers inherit it — default delegates to the
upserting update_session_metadata; ChatServer calls it. Postgres fake
runner now distinguishes DO NOTHING vs DO UPDATE. Contract asserted once in
the shared run_chat_history_conformance harness (covers all 4 drivers) +
real sqlite POST /sessions e2e via httpx ASGITransport. Fixed reference
_DictHistory + harness to list metadata-only sessions; flipped obsolete
postgres raise test. Full gate + Live CI green (58881e0). PR #64 open.
Next: bug-013 → enh-001; bug-008 before tag, then cut v0.2.4.

## 2026-06-03T05:30 — v0.2.4 cluster: bug-018 merged (#64), bug-013 opened (#65)
PR #64 (bug-018 chat session-create) merged to main (4c735d1). Started
bug-013 on `fix/bug-013-auto-register-tools` — P2 raw-factory foot-gun:
MCPServer.from_stdio/from_http held the tool list but never registered it,
so a factory-built server served an empty ListTools (the supported
MCPBridge path was unaffected — start() registers). Fix: factories call
register_tools() before returning; register_tools() idempotent via a
_registered guard (explicit extra call = no-op, 0); set_tools() re-arms
(bridge empty-placeholder → attach_local_tools → start() registers stays
correct); both factories gained runner= injection so the fix is
unit-tested (auto-register / idempotency / set_tools re-arm) not live-only.
feat-013 §10 + CHANGELOG + bug-013 doc. ALSO (user request): reinforced the
state-tracking cadence in-git — project .claude/state/README.md "When to
write" + workspace pipeline Rule 4 now state each PR open/merge is a
tracker milestone to commit+push (not batched to session end), esp. in a
multi-PR cluster. Full gate green (b13a096). PR #65 open. After merge the
bug cluster is DONE; remaining: enh-001 (may slip to 0.2.5), bug-008 (~5
lines) before tagging, then cut v0.2.4.

## 2026-06-03T06:30 — v0.2.4 cluster: bug-013 merged (#65); enh-001 + bug-008 opened (#66)
PR #65 (bug-013) merged to main (503ffdb) — all 8 cluster bugs now in.
Per user, bundled enh-001 + bug-008 into ONE PR with TWO commits on
`enh/001-mcp-http-server-transport`:
- enh-001 (e3497bd): MCP server-side HTTP transport. _SDKServerRunner.serve()
  branches stdio/http; http = StreamableHTTPSessionManager mounted at /mcp
  under uvicorn (stop() graceful); unsupported transport rejected at
  construction. Migrated the CLIENT http transport off the SDK's deprecated
  streamablehttp_client → streamable_http_client + create_mcp_http_client
  (the deprecation errored under filterwarnings=error and blocked the
  round-trip). starlette/uvicorn transitive via agentforge-mcp[mcp] — no new
  dep. Live HTTP round-trip test added + verified locally (RUN_LIVE_MCP=1).
  SSE server transport still deferred (phase 2).
- bug-008 (eaa2d3c): _template_version/_framework_version look up
  distribution name agentforge-py (not import name agentforge), so scaffolds
  record the real version not 0.0.0+unknown; regression test added.
PROCESS NOTE: both commits were briefly made on local main by mistake (forgot
to branch after #65 merge), then moved to the feature branch and main was
reset to origin/main BEFORE any push — zero remote impact. Reinforces the
"branch first" discipline. Full gate green. PR #66 open. AFTER it merges the
v0.2.4 cluster is DONE → cut v0.2.4 (CHANGELOG date, release notes,
pre-release checklist, tag, release.yml).

## 2026-06-03T07:30 — v0.2.4 release prep (PR #67); cluster complete
PR #66 (enh-001 + bug-008) merged to main (325e98f). The v0.2.4 cluster is
COMPLETE: all 8 bugs (012/013/014/015/017/018/019/020) + enh-001 merged;
34 pkgs at 0.2.4 on main. Opened `chore/release-v0.2.4` (PR #67) with the
reversible release prep: CHANGELOG `## [0.2.4]` dated 2026-06-03 (empty
`## [Unreleased]` already above it); `docs/releases/v0.2.4.md` written
(codename "Live-fire MCP", mirroring the v0.2.3 notes style); current.md +
this log synced. PAUSED before the irreversible steps per release policy:
(a) pre-release checklist §8 MANDATORY TestPyPI dry run
(`python scripts/testpypi_dry_run.py`) needs the user's TestPyPI creds;
(b) the v0.2.4 tag triggers release.yml → immutable PyPI publish of 34
packages. v0.2.4 is a new VERSION of existing projects so the new-project
quota does NOT apply (unlike the v0.2.1→0.2.3 drip). last_shipped will flip
to v0.2.4 only after the tag is pushed.

## 2026-06-03T07:30 — v0.2.4 RELEASED — Live-fire MCP
PR #67 (release prep) merged to main (6f208e9). Main CI green, then:
tagged `v0.2.4` at 6f208e9, pushed; `gh release create v0.2.4` published the
GitHub Release from docs/releases/v0.2.4.md. The tag triggered release.yml
(run 26869970428) → BOTH jobs (Build wheels+sdists, Publish to PyPI) SUCCESS
→ all 34 packages live on PyPI at 0.2.4 in ONE clean run. Verified on PyPI:
agentforge-py 0.2.4 (latest) + agentforge-mcp 0.2.4. First non-drip release
since the new-project-quota era — v0.2.4 is a new VERSION of existing
projects so the quota didn't apply.
Pre-release gates (all green): TestPyPI dry run (34 build+upload+smoke
install of agentforge-py[anthropic]==0.2.4 → import ok); real scaffold
(`agentforge new`) + upgrade (`agentforge upgrade --to 0.2.4`) + fork
end-to-end (managed files refreshed, forked preserved, bug-008 records
0.2.4 in situ); 46 scaffold/upgrade unit tests.
Shipped: 8-bug cluster (012/013/014/015/017/018/019/020) + enh-001 (MCP
HTTP server transport) + bug-008. State → idle.
Outstanding housekeeping (non-blocking): revoke ~/.pypirc [pypi] token,
confirm/convert Trusted Publishing, delete PYPI_PUBLISH_TRACKER.md.
