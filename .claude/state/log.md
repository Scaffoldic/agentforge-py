# Development log — append-only

This file is the chronological history of the AgentForge framework's
development. Every milestone, every shipped feature, every bug-carry
across features lands here. Newest entries at the bottom.

Format: `## YYYY-MM-DDTHH:MM — <event>` followed by 1-5 lines of detail.

---

## 2026-05-09T18:00 — Documentation phase complete

20 features specified, 20 ADRs locked, 5 design docs written, doc
templates and dev-pipeline scaffolding in place. Old a predecessor project docs archived
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
