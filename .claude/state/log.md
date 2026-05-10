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
