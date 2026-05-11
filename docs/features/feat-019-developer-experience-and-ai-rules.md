# feat-019: Developer experience — runbooks & AI assistant rules

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-019 |
| **Title** | Developer experience — runbook catalogue + `AGENTS.md` / `CLAUDE.md` rules in every scaffolded agent |
| **Status** | shipped (Python — 16 runbooks + AGENTS.md/CLAUDE.md/.cursorrules + `agentforge docs` CLI + three-section format) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 (initial set), continuously expanded |
| **Languages** | both (content is language-tagged inside) |
| **Module package(s)** | `agentforge-templates` (template repo); content delivered via scaffold |
| **Depends on** | feat-011 (Copier-based scaffolding), feat-017 (CLI) |
| **Blocks** | none |

---

## 1. Why this feature

A developer who scaffolds an agent at 9am should be productive by 11am.
Today, even on a well-designed framework, productivity is gated by the
developer learning the framework's conventions through trial and error.
That learning costs days. It costs more in teams: each developer
re-discovers the same conventions in slightly different ways, and the
agent codebase drifts away from the framework's intended shape.

There is also a 2026 reality the framework must engage with: most
developers are not editing alone. They are editing with Claude Code,
Cursor, GitHub Copilot, or another AI coding assistant. Without
framework-aware context, those assistants suggest patterns from
LangChain, generic Python idioms, or framework-incorrect approaches.
The developer accepts the suggestion, the project drifts, the framework's
guarantees erode.

The pain we are removing:

- "Where do I add a tool?" — answered by runbook 02 in 30 seconds, not
  30 minutes of reading source.
- "How do I switch from SQLite to Postgres?" — runbook 08 + one CLI
  command, not a manual rewrite.
- "Claude Code keeps suggesting LangChain patterns in my AgentForge
  project" — solved by `AGENTS.md` shipped with the scaffold telling
  the assistant the local conventions.
- Framework upgrade in six months — runbooks update with the framework
  via `agentforge upgrade`; the developer's mental model stays current
  for free.

## 2. Why it must ship as framework

- **Runbooks must mirror the framework as it evolves.** When feat-018
  adds a new safety validator, runbook 11 ("add safety guardrails")
  must reflect it. Per-team-authored runbooks would drift the moment
  the framework moves.
- **AI-assistant rules are a contract.** The framework owns the
  invariants (P1–P12, file ownership, locked surfaces). Per-team
  CLAUDE.md files would all drift slightly; AI assistants would behave
  differently across teams; cross-team code review would fight the
  drift.
- **Scaffolding delivers them automatically.** The `agentforge new`
  flow is the one moment the framework reliably has the developer's
  attention. Runbooks land in the project at that moment, marked as
  managed, and stay in sync forever via `agentforge upgrade`.
- **Upgrade-safe documentation.** Runbooks evolve; the framework
  owns evolution. Marker headers + Copier merge (feat-011) make
  documentation as upgrade-safe as code.
- **Without framework ownership:** every team writes their own
  CLAUDE.md, AI assistants suggest patterns at random, runbooks rot,
  knowledge is per-team folklore.

## 3. How derived agents benefit

- **Day 0 — runbooks ship pre-installed.** `agentforge new my-agent`
  produces a `docs/runbooks/` directory with task-oriented guides for
  every common operation. No googling, no Stack Overflow.
- **Day 0 — AI assistant knows the conventions.** `AGENTS.md` at the
  project root is read by Claude Code, Cursor, and other AI tools
  before any suggestion. The first prompt the developer types ("add a
  tool that calls our internal API") produces a framework-correct
  result.
- **Day 14 — onboarding a new team member.** Runbooks become the
  onboarding curriculum. Pair them with the AI assistant for an
  active learning experience.
- **Day 60 — adding a capability.** "How do I add MCP?" → `agentforge
  docs add-mcp` opens runbook 09; `AGENTS.md` ensures the assistant
  follows the same path. Two complementary surfaces.
- **Day 180 — framework upgrade.** `agentforge upgrade` merges new
  runbook content with the developer's customisations; `AGENTS.md`
  picks up the latest invariants. Stale documentation is impossible.
- **Day 365 — operations runbooks.** Same mechanism delivers runbooks
  for production ops (incidents, replay, db migration) — the team
  that built the agent and the team that operates it read from one
  source.

## 4. Feature specifications

### 4.1 User-facing experience

```bash
$ agentforge new my-pr-reviewer --template code-reviewer
  → ...
  → writing docs/runbooks/ ............. 16 runbooks
  → writing AGENTS.md, CLAUDE.md, .cursorrules
  → done.

$ tree docs/runbooks/
docs/runbooks/
├── README.md
├── 01-set-up-new-agent.md
├── 02-add-a-tool.md
├── 03-add-a-pipeline-task.md
├── 04-pick-reasoning-strategy.md
├── 05-write-prompts.md
├── 06-test-your-agent.md
├── 07-debug-a-run.md
├── 08-add-memory.md
├── 09-add-mcp.md
├── 10-add-evaluators.md
├── 11-add-safety-guardrails.md
├── 12-add-observability.md
├── 13-configure-multi-provider.md
├── 14-deploy-your-agent.md
├── 15-upgrade-your-agent.md
└── 16-configuration-reference.md

$ agentforge docs                      # interactive picker
$ agentforge docs add-mcp              # opens runbook 09
$ agentforge docs check                # diffs runbooks vs current framework
```

**AI assistant integration** is automatic — `AGENTS.md` at the project
root is read by Claude Code, Cursor, Aider, and any tool following the
emerging AGENTS.md convention. `CLAUDE.md` and `.cursorrules` ship as
thin pointers so each tool's native discovery still works.

### 4.2 Public API / contract

The "API" here is the structure of the documents themselves, since
they are read by both humans and AI tools.

**Runbook contract** (every runbook follows this shape):

```markdown
# NN — <Task>

> **Goal:** one-line description of what the developer accomplishes.
> **Time:** ~15 minutes.
> **Prereqs:** which runbooks should be done first (or "none").

## TL;DR

A 5-line code or command snippet that solves the common case.

## Step by step

Numbered. Code blocks. No prose paragraphs longer than 4 lines.

## Variations

Common deviations: alternative providers, optional config knobs.

## Troubleshooting

A table of `Symptom → Cause → Fix`.

## Related

- Other runbooks
- Feature docs
- Design docs

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- Anything below this line is owned by the developer; agentforge upgrade
     does not touch it. Use it for project-specific notes. -->
<!-- agentforge:end-custom -->
```

**`AGENTS.md` contract** (~150 lines, structured for AI consumption):

```markdown
# AgentForge agent — AI assistant instructions

This project is built on AgentForge {{framework_version}}. Use these rules
when suggesting changes.

## Project shape (you must respect this)

- Framework version: {{framework_version}}
- Template: {{template_name}}                 # code-reviewer | patch-bot | ...
- Active modules: {{module_list}}

## File ownership rules

- Files starting with `AGENTFORGE-MANAGED:` are owned by the framework. Do not
  edit. Suggest changes to YAML config or developer-owned files instead.
- Files starting with `AGENTFORGE-FORKED:` were customised by the developer.
  Edit normally; do not restore the marker.
- Files with no marker are developer-owned. Edit normally.

## Architecture invariants

- Tools: `@tool` decorator on a typed function, OR subclass `Tool`. Type hints
  drive the input schema; no hand-written JSON schemas.
- Reasoning loop: do not edit; configure via `agentforge.yaml > agent.strategy`.
- LLM clients: do not import vendor SDKs directly. Use `agent.providers["..."]`
  or pass `model="<provider>:<model_id>"`.
- Memory: do not write SQL directly. Use `agent.memory.put / .get / .query`.
- Costs: do not bypass `BudgetPolicy`. Every LLM call is checked.
- Run id: do not invent your own correlation id. Use `current_run().run_id`.

## How to add common things (open the runbook for detail)

| Task | Runbook |
|---|---|
| Add a tool | docs/runbooks/02-add-a-tool.md |
| Add a pipeline task | docs/runbooks/03-add-a-pipeline-task.md |
| Switch reasoning strategy | docs/runbooks/04-pick-reasoning-strategy.md |
| Add memory / persistence | docs/runbooks/08-add-memory.md |
| Add MCP servers | docs/runbooks/09-add-mcp.md |
| Add evaluators | docs/runbooks/10-add-evaluators.md |
| Add safety guardrails | docs/runbooks/11-add-safety-guardrails.md |
| Add observability backend | docs/runbooks/12-add-observability.md |
| Configure multi-provider | docs/runbooks/13-configure-multi-provider.md |

## Anti-patterns (do not suggest these)

- LangChain idioms (`LCEL`, `Runnable`, `RunnablePassthrough`) — wrong framework.
- Hand-rolling JSON schemas for tools — use type hints.
- Storing API keys in `agentforge.yaml` literals — use `${ENV_VAR}`.
- Catching exceptions inside tool code to "make the agent more robust" —
  let them surface; the framework records them as observations and the LLM
  recovers.
- Adding a wrapper around `Agent.run()` to add logging — the framework already
  logs; use a custom hook (runbook 12).

## Pre-commit checks (run these before suggesting a commit)

- `agentforge config validate`
- `agentforge status`        # check no managed file is silently modified
- `pytest -q`
- `ruff check`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- Project-specific instructions go here. Survives upgrades. -->
<!-- agentforge:end-custom -->
```

**`CLAUDE.md`** ships as a thin wrapper:

```markdown
> See [AGENTS.md](./AGENTS.md) for AgentForge conventions. Claude Code reads
> both files; AGENTS.md is the canonical source.

<!-- agentforge:custom -->
<!-- Add Claude Code-specific instructions here. -->
<!-- agentforge:end-custom -->
```

**`.cursorrules`** ditto:

```
See AGENTS.md for project conventions. AGENTS.md is the canonical source.
```

### 4.3 Internal mechanics

**Authoring location:** runbooks and `AGENTS.md` source live in
`agentforge-templates/_shared/` (shared across all templates) or in
`agentforge-templates/<template_name>/` (template-specific). The Copier
template renders them into the developer's project at scaffold time.

**Variable expansion:** runbook and `AGENTS.md` content is Jinja-rendered
with `{{framework_version}}`, `{{template_name}}`, `{{module_list}}`,
etc. — so the rendered content matches the actual project state.

**Three-section file format:**

```
[ marker header ]
AGENTFORGE-MANAGED: agentforge-templates@0.5.1 hash:<sha>

[ managed content ]
... rendered by Copier; updated by `agentforge upgrade`

<!-- agentforge:end-managed -->

[ custom content ]
<!-- agentforge:custom -->
... developer's notes, never touched by upgrade
<!-- agentforge:end-custom -->
```

`agentforge upgrade` updates the managed section, leaves the custom
section untouched. If the developer edits inside the managed section
(against guidance), the upgrade surfaces a conflict (per feat-011).

**`agentforge docs` CLI:**

- `docs` — interactive runbook picker
- `docs <topic>` — open by name (matches runbook filename or alias)
- `docs check` — compare local runbook hashes against framework's
  current; report drift; suggest `agentforge upgrade` if behind
- `docs serve` — local HTTP browser of the runbook tree (nice for
  multi-developer teams)

### 4.4 Module packaging

Content lives in `agentforge-templates` (a git repo, not a pip package).
The CLI `agentforge docs` ships in `agentforge`. No new pip module.

### 4.5 Configuration

```yaml
# agentforge.yaml
docs:
  runbooks_path: "./docs/runbooks"      # default
  agents_md_path: "./AGENTS.md"
  open_command: "auto"                   # "auto" | "less" | "code" | "browser"
```

The `open_command` is honoured by `agentforge docs <topic>`.

## 5. Plug-and-play & upgrade story

Always shipped via scaffolding. `agentforge upgrade` merges runbook
content via the same marker-header mechanism as code (feat-011). New
runbooks added by the framework appear in the developer's project on
upgrade with full content. Removed runbooks (rare) are deleted with
notice; renamed runbooks redirect.

A developer who wants to fully customise a runbook runs
`agentforge fork docs/runbooks/02-add-a-tool.md` — same `fork` flow as
any other managed file.

## 6. Cross-language parity

Runbook content is largely language-tagged with code blocks for both
Python and TypeScript. Single source authored once; rendered with
`{{language}}` filtering for projects targeting one language only —
shows only relevant code blocks, drops the other.

`AGENTS.md` ships in both — same structure, language-appropriate
examples.

## 7. Test strategy

- **Render check:** every runbook in `agentforge-templates` Jinja-
  renders without error against every template's variables.
- **Link check:** every runbook reference resolves; no dangling links
  to runbooks that don't exist.
- **AI-rules conformance:** `AGENTS.md` "anti-patterns" section
  enumerated against an automated linter that catches the most common
  ones — runbook claims and lint rules stay aligned.
- **Upgrade test:** generate on v0.x with custom content in custom
  sections; upgrade to v0.y; verify custom sections preserved.
- **Spot-check with assistant:** during release prep, have Claude Code
  use a fresh scaffold; confirm it follows `AGENTS.md` (smoke check
  for AI-readability).

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| `AGENTS.md` becomes too long; AI assistants truncate | Hard 200-line cap; runbooks for detail; structure scannable (tables + bullets); periodic length audit |
| Documentation drifts from code | Every feature merge requires an updated runbook entry (CI check that referenced features have a runbook); release blocked otherwise |
| Multiple AI tools want different file names | AGENTS.md as universal canonical; CLAUDE.md / .cursorrules as thin pointers; new tools added on demand |
| Localisation (non-English teams) | Out of scope at v0.x; English only; community can fork |
| Should we ship video / interactive tutorials? | No — text + code is enough; videos rot faster than text |
| Per-template runbook differences (code-reviewer vs research) | Shared base + per-template addendum; both ship in the scaffold |
| Custom-section markers break developer's markdown linter | Markers are valid HTML comments; documented; common linters handled |
| AI assistant ignores `AGENTS.md` and uses cached LangChain knowledge | Mitigation is honest: `AGENTS.md` reduces the failure rate but cannot prevent it. Recommend developers review AI suggestions; runbooks help the developer catch drift. |
| Runbook number reuse when a runbook is removed | Numbers immutable; removed runbooks become a tombstone with a redirect; no renumbering |

## 9. Out of scope

- A central documentation portal (read-the-docs style site for the
  framework). Different concern: the *framework's* docs are at
  `docs.agentforge.dev`; this feature is about docs *inside generated
  projects*.
- API reference auto-generation. Dependent on the implementation; we
  generate once code exists, hosted at the framework's docs site.
- IDE-specific snippet packages (VS Code snippets, JetBrains live
  templates). Out of scope; AI assistants supersede static snippets.
- Voice / video tutorials.
- Translation / i18n.

## 10. Implementation status (Python)

Shipped in PR #23. The framework's six scaffolding templates
(feat-011) now produce projects that include the runbooks +
AGENTS.md + CLAUDE.md + .cursorrules out of the box, plus the
`agentforge docs` CLI for opening / auditing them.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `85aaf70` | Three-section managed/custom file format (`split_three_section` / `merge_three_section`, `<!-- agentforge:end-managed -->` / `<!-- agentforge:custom -->` markers). |
| 2 | `58663de` | `inject_shared_scaffold(dst, template_name, template_version)` post-render hook. Walks `agentforge.templates._shared`, renders `.tmpl` files through Jinja with the Copier answer file as context, prepends marker headers, extends the managed-files lock. |
| 3 | `5302bc1` | AGENTS.md / CLAUDE.md / .cursorrules content (~150 lines AGENTS.md with project shape, ownership, invariants, runbook table, anti-patterns, pre-commit; thin pointer wrappers for CLAUDE.md + .cursorrules). |
| 4 | `8cf6412` | Runbooks 01-05 (set up, add a tool, add a pipeline task, pick reasoning strategy, write prompts). |
| 5 | `f5d4812` | Runbooks 06-10 (test, debug, add memory, add MCP, add evaluators). |
| 6 | `7d03021` | Runbooks 11-16 + index README (safety guardrails, observability, multi-provider, deploy, upgrade, configuration reference; README.md.tmpl). |
| 7 | `1cc3fa9` | `agentforge docs` CLI — list / open / `--check` (drift vs framework bundle) / `--serve` (local HTTP). |
| 8 | (this PR) | Spec status + Implementation Status + Runbook + roadmap + CHANGELOG + state. |

### Deviations from the design

- **Shared injection is a post-Copier step, not Copier
  primitives.** Copier doesn't have a clean `_extra_paths` for
  cross-template shared content. We render after Copier
  finishes, using the same answers file. End-effect for the
  developer is identical.
- **Modules list in `AGENTS.md`** ships as an empty list today
  — populating it requires reading `pyproject.toml`
  dependencies + the configured `modules.*` blocks, which is
  follow-up work. The runbook tables and anti-patterns are the
  load-bearing content.
- **`agentforge docs serve` is a stdlib
  `SimpleHTTPRequestHandler`** — fine for local browsing; no
  fancy rendering. A markdown renderer is a v0.2 follow-up.
- **No CI link-check yet.** Runbooks reference each other and
  feature specs; broken links surface in `agentforge docs
  --check` only when content hashes change. A dedicated
  link-resolver test lands in a follow-up.
- **TypeScript port deferred.** Runbook content is written
  language-neutrally where possible; feat-019's TS counterpart
  will swap code blocks once feat-011's TS scaffolding engine
  (ADR-0021) ships.

### Three-section file format (locked)

Markdown documents managed by the framework end with:

```
... framework content ...

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- developer-owned section; survives `agentforge upgrade` -->
<!-- agentforge:end-custom -->
```

`split_three_section(content) -> (managed, custom)` and
`merge_three_section(new_managed, existing_custom) -> str` are
the contract; `agentforge upgrade` (feat-011) consumes them when
re-rendering a managed file.

### Shared payload location

`packages/agentforge/src/agentforge/templates/_shared/`:

- `AGENTS.md.tmpl` (Jinja: framework_version, template_name,
  project_slug, llm_provider)
- `CLAUDE.md`
- `.cursorrules`
- `docs/runbooks/README.md.tmpl`
- `docs/runbooks/01-set-up-new-agent.md.tmpl` (Jinja:
  project_slug)
- `docs/runbooks/02-add-a-tool.md`
- `docs/runbooks/03-add-a-pipeline-task.md`
- … (through 16)

## 11. Runbook

### Open a runbook

```bash
agentforge docs                       # list every runbook
agentforge docs 02                    # open by number
agentforge docs add-tool              # open by alias
agentforge docs 02-add-a-tool.md      # open by exact name
```

`$EDITOR` opens in your preferred editor when set; otherwise
the runbook prints to stdout (handy with `| less`).

### Check for drift against the framework bundle

```bash
agentforge docs --check
```

Hashes each local runbook with the marker line stripped, then
compares to the bundled copy inside the installed `agentforge`
wheel. Reports `~drift` for changed content and `+local` for
runbooks that exist locally but not in the bundle. Exits 1 when
drift is detected.

### Customise a runbook

Edit anything BELOW the `<!-- agentforge:end-managed -->` marker.
Content there survives `agentforge upgrade`. Touching the
managed section will surface as a `.rej` conflict on the next
upgrade (intentional — the framework owns that part).

To take over a runbook entirely:

```bash
agentforge fork docs/runbooks/02-add-a-tool.md
```

Future upgrades skip it. Reverse with `agentforge unfork
<path>`.

### Update AI rules

`AGENTS.md` ships managed by the framework. Project-specific
rules go in the custom section at the bottom — Claude Code,
Cursor, and Aider all read the whole file, so your additions
are visible immediately.

When the framework adds a new architecture invariant, the
managed section refreshes automatically on upgrade.

## 12. References

- [`scaffolding-and-upgrade.md`](../design/scaffolding-and-upgrade.md) — the
  Copier mechanism and marker-header file ownership
- [`design-principles.md`](../design/design-principles.md) — every runbook
  is implicitly an exposition of one or more principles
- feat-011 (`agentforge new` and `agentforge upgrade`)
- feat-017 (`agentforge docs` subcommand)
- AGENTS.md emerging convention: https://agents.md (community-driven
  tool-agnostic spec)
- Claude Code memory/instructions docs: https://docs.claude.com/en/docs/claude-code
- Cursor rules: https://docs.cursor.com/context/rules-for-ai
