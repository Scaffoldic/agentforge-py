# Design Doc: Scaffolding & Upgrade

## Metadata

| Field | Value |
|---|---|
| **Title** | Scaffolding & Upgrade — `agentforge new`, `agentforge add`, `agentforge upgrade` |
| **Status** | draft |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Last updated** | 2026-05-09 |
| **Supersedes** | none |
| **Superseded by** | none |
| **Related features** | feat-011 (scaffolding & upgrade), feat-010 (module CLI) |

---

## 1. Context

A developer's experience with AgentForge has three milestones:

1. **Day 1 — `agentforge new`.** Generate a new agent project from a template.
2. **Day 30 — `agentforge add module <X>`.** Add a capability they didn't pick on
   day 1.
3. **Day 180 — `agentforge upgrade`.** Pull in framework improvements without
   breaking anything they've built.

Existing frameworks handle (1) well (cookiecutter, `crewai create`, `strands new`).
A few handle (2) well (CrewAI's tools-extras, smolagents Hub). **Almost none handle
(3) without a manual diff** — and that is exactly the moment a long-lived agent's
maintainer reaches for the framework, gets burned, and stays on an old version
forever. a predecessor project's `template-sync` was an attempt to solve this; it is incomplete.

This doc is the design that makes (3) actually work, by picking the right tool
(Copier) and laying down the file conventions (marker headers + ownership model)
that make automated upgrades safe.

## 2. Goals

- `agentforge new` produces a working agent in &lt; 60 seconds with sensible
  defaults and no required prompts beyond name/template/language.
- `agentforge add module <X>` (covered in `module-system.md`) integrates with the
  same scaffolding mechanism — a module's manifest is just a partial template.
- `agentforge upgrade` pulls in framework improvements with three-way merge.
  Developer-edited managed files surface as conflicts; un-edited managed files
  update silently; developer-owned files are never touched.
- The upgrade story works the same in Python and TypeScript.
- A developer can `agentforge fork <file>` to take ownership of any managed file,
  trading future automatic updates for full control.

## 3. Non-goals

- Reverting an upgrade. Once applied, an upgrade is just a commit; rollback is via
  the developer's VCS, not via `agentforge`.
- Cross-template migrations (e.g. moving from `code-reviewer` template to
  `research` template). Templates are starting points; once you've started, you've
  started.
- Migrations of *config* schema across major framework versions. Major bumps may
  require config edits; we provide a `agentforge config migrate` helper but do not
  promise zero-touch.

## 4. Proposal

### 4.1 Tool choice — Copier, not Cookiecutter

| Aspect | Cookiecutter | Copier |
|---|---|---|
| Generate from template | yes | yes |
| **Update existing project** | no | **yes** — three-way merge built in |
| Keep template ↔ project linked | no | yes (via `.copier-answers.yml`) |
| Conditional prompting | basic | yes (Jinja in questions) |
| Multi-language template | possible | natively supported |
| Maintenance burden of upgrade | manual diff every time | automatic merge |

We use **Copier**. The fact that Copier is purpose-built for the upgrade case is
decisive — and it is what `cruft` was bolted onto Cookiecutter to provide, except
without the bolt.

In TypeScript, we wrap Copier (Python tool) inside the `agentforge` Node CLI, or
use a TS-native equivalent (`degit-style + custom diff`) — open question 8.1.

### 4.2 Template repository layout

```
agentforge-templates/                  # one git repo, multiple templates
├── copier.yml                         # shared config, common questions
├── code-reviewer/
│   ├── copier.yml                     # template-specific extras
│   └── {{project_name}}/              # project skeleton
│       ├── agentforge.yaml.jinja
│       ├── pyproject.toml.jinja
│       ├── src/
│       │   └── {{module_name}}/
│       │       ├── tools/
│       │       ├── prompts/
│       │       └── pipeline/
│       ├── tests/
│       └── README.md.jinja
├── patch-bot/
├── docs-qa/
├── triage/
├── research/
└── minimal/
```

Six starter templates correspond to the five legacy archetypes plus a `minimal`
variant for developers who want no scaffolding noise.

### 4.3 The `.agentforge-state` directory

Every generated project gets a hidden directory:

```
.agentforge-state/
├── answers.yml                # Copier's answer file (linked to template)
├── manifests/                 # snapshot of every module's manifest at install
│   ├── memory-postgres.yaml
│   └── mcp.yaml
└── managed-files.lock         # hash of every managed file at last upgrade
```

This is the framework's source of truth about "what state is this project in?" —
checked into git, versioned with the project, and read by `agentforge upgrade` and
`agentforge add module`.

### 4.4 File ownership model

Every file in a generated project is one of three classes:

| Class | Marker | Updated by `agentforge upgrade`? | Updated by `agentforge add module`? |
|---|---|---|---|
| **Managed** | header `AGENTFORGE-MANAGED: <module>@<version> hash:<sha>` | yes — three-way merge if hash matches | yes — added/modified per module manifest |
| **Forked** | header `AGENTFORGE-FORKED: <module>@<version> at <date>` | no | no |
| **Owned** | no header | no | no |

The header lives in the file's native comment syntax (`#`, `//`, `--`, `<!--`).
Not all file types support comments (binary files, JSON without comments); for
those, the manifest declares them as `managed: by-presence` — ownership is tracked
in `.agentforge-state/managed-files.lock`, not inline.

### 4.5 The upgrade flow

```
$ agentforge upgrade

  → reading .agentforge-state/answers.yml ............ 0.4.2 → 0.5.1
  → fetching new framework template at 0.5.1 ......... ok
  → planning diff:
       managed files unchanged in your repo: 14
       managed files locally modified:        2 — will three-way merge
       new files added by template:           3
       files removed by template:             1 (deprecated)

  Proceed? [Y/n]: y

  → applying:
       MERGED  src/myagent/agent_runtime.py     (clean)
       MERGED  agentforge.yaml                  (clean)
       ADDED   .agentforge-state/manifests/mcp-protocol.yaml
       ADDED   src/myagent/protocols/.gitkeep
       ADDED   docs/runbooks/mcp.md
       REMOVED .agentforge-state/legacy-marker

  → updating .agentforge-state/answers.yml ........... 0.5.1
  → updating .agentforge-state/managed-files.lock .... 16 entries
  → done in 2.4s

  Next: review the merged files, run tests, commit.
```

If a three-way merge cannot resolve cleanly:

```
  ! CONFLICT in src/myagent/agent_runtime.py
    Your version differs from the 0.4.2 baseline AND the 0.5.1 template
    differs from it. The framework cannot reconcile automatically.

  Choose:
    [m] open in your $MERGETOOL                    (recommended)
    [t] take the template version (lose your edits)
    [k] keep your version (skip this file's update)
    [f] fork this file (this commit and forever)
```

`[f]` adds the `AGENTFORGE-FORKED` header and updates the lock; future upgrades
skip the file.

### 4.6 The `agentforge fork` command

Sometimes a developer knows up front they need to customise a managed file beyond
what config can express. `agentforge fork <path>` claims the file:

```
$ agentforge fork src/myagent/agent_runtime.py

  → src/myagent/agent_runtime.py is currently managed by agentforge@0.4.2
  → adding AGENTFORGE-FORKED header
  → updating .agentforge-state/managed-files.lock
  → done. This file will not be updated by future `agentforge upgrade` runs.

  To unfork later:
    agentforge unfork src/myagent/agent_runtime.py
  (this restores the file to the latest template version, losing your edits)
```

### 4.7 The `agentforge new` flow

```
$ agentforge new my-pr-reviewer

  ? Template:        code-reviewer
  ? Language:        python
  ? LLM provider:    anthropic
  ? Persistence:     none (you can add this later with `agentforge add module`)

  → cloning template ...................... ok
  → installing agentforge[anthropic] ...... ok
  → writing .agentforge-state/answers.yml . ok
  → done in 18s

  Next:
    cd my-pr-reviewer
    cp .env.example .env && edit ANTHROPIC_API_KEY
    agentforge run "review this PR: ..."
```

The prompts are answerable in batch:

```
$ agentforge new my-pr-reviewer --template code-reviewer --language python --provider anthropic
```

### 4.8 The `agentforge add module` flow (covered in module-system.md, summarised here)

```
$ agentforge add module memory-postgres

  → installing agentforge-memory-postgres ............... 0.5.1
  → reading manifest .................................... ok
  → writing .agentforge-state/manifests/memory-postgres.yaml
  → applying manifest:
       APPENDED  .env.example                            (POSTGRES_DSN)
       ADDED     db/migrations/agentforge/0001_init.sql  (managed)
       ADDED     db/migrations/agentforge/0002_idx.sql   (managed)
       ADDED     scripts/db_migrate.py                   (managed)
       MODIFIED  agentforge.yaml                         (modules.memory)
  → done.

  Next:
    1. Set POSTGRES_DSN in .env
    2. Run: agentforge db migrate
```

### 4.9 Cross-language: how does this work in TypeScript?

Two options, decided in feat-011:

- **Option A — wrap Copier.** The TS CLI shells out to Copier (assumes Python is
  available). Pro: one mechanism. Con: TS users must install Python.
- **Option B — TS-native template engine.** Build a small Copier-equivalent in TS
  using the same template format. Pro: no Python dependency. Con: another tool to
  maintain.

Recommendation: **Option A** for v0.x (faster to ship); revisit Option B once we
have signal on how many TS-only users we have.

## 5. Alternatives considered

| Option | Why we didn't pick it |
|---|---|
| Cookiecutter only | Cannot update; defeats the whole goal |
| `cruft` (Cookiecutter + update tracker) | Works but is essentially Copier-with-extra-steps; Copier is more mature |
| Vendored framework code (Atomic Agents model) | Auditability is real but the upgrade burden is high; our users prefer pip-install for framework primitives |
| Plain git-based template + manual rebase | Effectively what a predecessor project's `template-sync` was; works for power users, fails for the median |
| No upgrade story; force re-scaffold | Loses every customisation. Non-starter for production agents. |

## 6. Migration / rollout

- **v0.1.** `agentforge new` only. Six templates: code-reviewer, patch-bot,
  docs-qa, triage, research, minimal.
- **v0.2.** `agentforge add module`, `agentforge swap`, `agentforge fork`.
- **v0.3.** `agentforge upgrade` with three-way merge.
- **v0.4.** `agentforge migrate from-legacy` for a predecessor project agents that want to come over.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Three-way merge produces silent semantic conflicts even when text-merge is clean | After every upgrade, the framework runs the project's test suite; report failures in the upgrade summary |
| Marker headers are stripped by code formatters | Marker is the first line of the file (or first line after shebang/encoding); pre-commit hook restores it; conformance test verifies presence |
| Developers fork everything to avoid conflicts, then never get framework improvements | `agentforge status` warns when forked files lag the latest template by &gt; N versions; we don't block, we surface |
| Copier is a Python-only tool; TS users hit friction | Bundle Copier into the npm package via `python-shell` initially; native TS port deferred |
| `.agentforge-state/` directory drifts from reality (developer edits without CLI) | `agentforge status` reconciles by re-hashing managed files; suspicious mismatches flagged |
| Template repo becomes a fragile dependency at upgrade time | Pin template version in `.agentforge-state/answers.yml`; cache locally; allow offline upgrades from cache |

## 8. Open questions

1. **Python-only vs TS-native upgrade tool.** See §4.9. Decide before feat-011
   implementation begins.
2. **Should the upgrade run tests automatically?** Pro: catches semantic
   regressions. Con: slow, requires a working test setup. Lean: opt-in flag
   `agentforge upgrade --run-tests`.
3. **What happens to a forked file when the template removes its origin?** Edge
   case: developer forks `db/migrations/agentforge/0003.sql`, then 0.6 removes
   that migration. Lean: `agentforge status` reports it as orphaned; developer
   decides.
4. **How do we test the upgrade story?** End-to-end: spin up an agent on every
   prior version in CI, run `agentforge upgrade` to current, verify it succeeds.
   Track in feat-011 test plan.

## 9. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-09 | Use Copier as the scaffolding/upgrade engine | Purpose-built for the update-after-generate case; mature; the only tool that doesn't require us to bolt on the upgrade mechanism ourselves |
| 2026-05-09 | Three file classes: managed / forked / owned | Maps cleanly onto "framework owns this", "developer claimed it", "developer authored it from scratch" |
| 2026-05-09 | Inline marker headers + `.agentforge-state/managed-files.lock` | Header is human-readable and survives moves; lock file handles binary/JSON files where comments aren't possible |
| 2026-05-09 | Six starter templates at v0.1 | Covers the legacy archetypes; `minimal` covers the "I want no boilerplate" case |
| 2026-05-09 | Wrap Copier from the TS CLI initially (Option A) | Faster to ship; native TS port revisited after first user signal |

## 10. References

- [`architecture.md`](./architecture.md)
- [`module-system.md`](./module-system.md) — how `agentforge add module` ties into module manifests
- [`design-principles.md`](./design-principles.md) — P2 (modules pip-installable, not scaffolded), P8 (upgrade-safe by construction)
- [Copier docs](https://copier.readthedocs.io/) — the underlying engine
- Archived predecessor: `docs/archive/template-sync.md` — a predecessor project's incomplete answer to this problem
