# feat-011: Scaffolding & upgrade

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-011 |
| **Title** | Scaffolding & upgrade — `agentforge new`, `agentforge upgrade`, `agentforge fork`, six starter templates |
| **Status** | shipped (Python — `new` + 6 templates + `upgrade` + `fork`/`unfork`/`status`) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 (`new` + 6 templates + `upgrade` + `fork` / `unfork` / `status` — all shipped) |
| **Languages** | both |
| **Module package(s)** | `agentforge` (CLI), `agentforge-templates` (template repo) |
| **Depends on** | feat-010 |
| **Blocks** | none |

---

## 1. Why this feature

A blank editor is intimidating. Most agent projects fail before they begin
because the developer doesn't know "where do I put the prompt? where do I
register a tool? where does config go?" Every framework that ships well-
adopted gives a `framework new` command for a reason — it removes the
blank-page problem.

But the bigger pain is on Day 180. The developer has shipped, customised, and
operated their agent. The framework releases v0.5 with bug fixes and new
features. Today, they either manually port the changes (slow, error-prone) or
stay on v0.4 forever (technical debt accrues; security patches missed).
EVA's `eva-template-sync` was an attempt; it's incomplete. Most other
frameworks don't even try.

## 2. Why it must ship as framework

- **The scaffold-vs-update tension only resolves at the framework layer.**
  Boilerplate is owned by the framework (so updates can apply); custom
  code is owned by the developer (so updates leave it alone). That ownership
  model has to be uniform across all generated projects.
- **Marker headers** + `.agentforge-state/managed-files.lock` are protocol
  between scaffolding and upgrade. If each agent invented its own, upgrades
  couldn't reason about ownership.
- **Templates evolve in lockstep with framework features.** When feat-005
  adds a new `MemoryStore` capability, the template's `agentforge.yaml`
  example reflects it. Templates are part of the framework release.
- **Without framework ownership:** every agent ages alone, drifts further
  from the framework, and eventually requires a "rewrite from scratch on
  the new template" migration.

## 3. How derived agents benefit

- **Day 1 — `agentforge new my-agent` produces a working project in 60s.**
  Six templates: code-reviewer, patch-bot, docs-qa, triage, research,
  minimal.
- **Day 90 — `agentforge add module mcp` reuses the same machinery.** No
  separate flow.
- **Day 180 — `agentforge upgrade` is one command.** Three-way merge for
  managed files; developer-owned files untouched.
- **Day 200 — needs to customise something the template owns.**
  `agentforge fork src/myagent/runtime.py` claims the file; future
  upgrades skip it.
- **Day 365 — agent has been operated for a year and is on the latest
  framework.** Without rewrite. This is the single biggest differentiator
  vs every other framework.

## 4. Feature specifications

### 4.1 User-facing experience

```bash
$ agentforge new my-pr-reviewer
? Template:        code-reviewer
? Language:        python
? LLM provider:    anthropic
? Persistence:     none

  → cloning template ........ ok
  → installing dependencies . ok
  → done in 18s
  Next: cd my-pr-reviewer && agentforge run "review this PR..."

$ agentforge upgrade
  → 0.4.2 → 0.5.1
  → managed files: 14 unchanged, 2 to merge
  → 3 new files, 1 removed
  Proceed? [Y/n]: y
  → done.

$ agentforge fork src/myagent/agent_runtime.py
  → marked as forked. Future upgrades will skip this file.
```

### 4.2 Public API / contract

CLI surface (locked from v0.1 onward):

```bash
agentforge new <name>
    [--template <code-reviewer | patch-bot | docs-qa | triage | research | minimal>]
    [--language <python | typescript>]
    [--provider <anthropic | bedrock | openai | ...>]
    [--no-prompts]            # batch mode

agentforge upgrade
    [--to <version>]          # default: latest
    [--dry-run]               # show what would change
    [--run-tests]

agentforge fork <path>
agentforge unfork <path>      # restore to template version (lossy)

agentforge status             # what's managed, what's forked, what's drifted
```

`.agentforge-state/` shape (locked):

```
.agentforge-state/
├── answers.yml               Copier answer file
├── manifests/                snapshot of every installed module's manifest
└── managed-files.lock        { path: { hash, source_module, source_version } }
```

Marker header (locked):

```
AGENTFORGE-MANAGED: <module>@<version> hash:<sha256-prefix>
```

### 4.3 Internal mechanics

See [`scaffolding-and-upgrade.md`](../design/scaffolding-and-upgrade.md)
§4.4–§4.6 for the full mechanism. Summary:

- **`agentforge new`** runs Copier with a template from
  `agentforge-templates`. Writes `.agentforge-state/answers.yml`.
- **`agentforge upgrade`** runs `copier update` against the linked template;
  three-way merges managed files; preserves forked + owned files; updates
  the lock.
- **`agentforge fork`** strips the marker header, updates lock to mark file
  as forked.

### 4.4 Module packaging

- `agentforge` ships the CLI subcommands.
- `agentforge-templates` is a git repo (not a pip / npm package) —
  cloned directly by both engines.
- **Python engine**: Copier (per ADR-0005).
- **TypeScript engine**: native TS port (per ADR-0021) consuming the
  same template format. Two engines, one template source of truth.

### 4.5 Configuration

The scaffold is itself the configuration. Once `agentforge new` runs, the
generated project has:

- `agentforge.yaml` — agent + module config
- `pyproject.toml` / `package.json` — dependencies
- `.env.example` — env vars
- `.agentforge-state/` — framework state
- `src/{agent}/` — developer code (tools, prompts, tasks)
- `tests/` — test scaffold
- `docs/runbooks/` — 16 task-oriented guides (managed by feat-019)
- `AGENTS.md` + `CLAUDE.md` + `.cursorrules` — AI-assistant rules so
  Claude Code, Cursor, etc. know the framework's conventions before
  the developer writes their first line (managed by feat-019)

## 5. Plug-and-play & upgrade story

`agentforge new` and `agentforge upgrade` *are* the upgrade story. The
mechanism extends naturally to module installs (`agentforge add module`
applies a partial template) and config swaps.

## 6. Cross-language parity

CLI commands identical. Templates ship in both languages from v0.1.
Two engines: Copier in Python (ADR-0005); native TS port (ADR-0021)
implementing the same template format and three-way merge semantics.
TS users have zero Python footprint.

A shared test-fixture suite verifies behavioural equivalence: every
fixture renders identically through both engines; every upgrade
scenario produces the same result. Drift between engines is a CI
failure.

## 7. Test strategy

- **Generation:** `agentforge new --no-prompts` for every template; the
  generated project's tests pass.
- **Upgrade smoke:** generate on v0.x, manually edit a managed file,
  upgrade to v0.y, verify three-way merge resolved cleanly.
- **Fork roundtrip:** fork a file, upgrade, verify file unchanged; unfork,
  verify restored.
- **Manifest application from a real module:** `agentforge add module
  memory-postgres` writes the expected files.
- **CI matrix:** every prior version × upgrade-to-current must succeed.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Three-way merge produces silent semantic conflicts | `agentforge upgrade --run-tests` opt-in; document the recommendation |
| Marker headers stripped by formatters | Pre-commit hook restores them; conformance test verifies presence |
| TS users without Python installed | Resolved (ADR-0021): native TS port from v0.x; no Python required |
| Template repo as a fragile dep | Pin template version in `.agentforge-state/answers.yml`; cache locally |
| Conflict on a managed migration file the user can't merge | Surface as conflict; offer `fork` option; document |
| Six templates to maintain — drift between them | Shared helpers in template; CI smoke-test each template on every framework change |

## 9. Out of scope

- Reverting an upgrade beyond `git revert`. The framework doesn't track
  history.
- Cross-template migration (move from `code-reviewer` to `research`).
  Templates are starting points only.
- Auto-detection of "missing optimisation" (e.g. "this agent could benefit
  from caching"). Out of scope; future linter-style tool.

## 10. Implementation status (Python)

Shipped in PR #19 against the `agentforge` package — CLI commands
`new`, `upgrade`, `fork`, `unfork`, `status` plus six starter
templates rendered via Copier.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `d07714e` | Copier dep + `agentforge new` + `minimal` template + 6 unit tests |
| 2 | `1207568` | 5 more templates (`code-reviewer`, `patch-bot`, `docs-qa`, `triage`, `research`) + parametrised template smoke tests |
| 3–5 | `9ce6a5c` | `.agentforge-state/managed-files.lock` + marker headers + `upgrade` (Copier three-way merge) + `fork`/`unfork`/`status` + 23 unit tests |
| 6 | (this PR) | Spec status + Runbook + roadmap + CHANGELOG + state files |

### Deviations from the design

- **Templates ship inside the `agentforge` wheel**, not from a
  separate `agentforge-templates` repo. The spec's §4.4 design
  anticipated cloning a git repo; instead Copier renders from
  `importlib.resources.files("agentforge.templates")`. This keeps
  v0.x installs self-contained — no network for `agentforge new`,
  no version-skew between framework and templates. The git-repo
  story stays available for v1.x if independent template versioning
  becomes valuable.
- **`agentforge upgrade` does not pin a specific framework version.**
  `--to` is plumbed through to Copier's `vcs_ref`, but with
  in-wheel templates there is no separate template version to pin
  yet. When templates move out-of-tree this knob becomes load-
  bearing; today it is forward-compatible.
- **`unfork` is partially restorative.** It re-prepends the marker
  and updates the lock but does not re-render template content; the
  user runs `agentforge upgrade` afterwards to pull template
  content. The spec's "(lossy)" caveat applies — this implementation
  defers the lossy overwrite to upgrade rather than doing it
  in-place.
- **No `--run-tests` flag on `upgrade` yet.** Surfaced as an open
  question in §8; deferred until the test-runner integration
  (post-feat-019) lands.

### Not implemented (deferred)

- **TypeScript engine (ADR-0021).** Out-of-scope for this PR; the
  Python implementation defines the on-disk contract (lock file
  shape + marker header format) the TS engine will mirror.
- **`agentforge add module` reusing the same machinery (§3).**
  Wired up against feat-012's module registry in a follow-up.
- **CI upgrade matrix (§7).** No prior versions to upgrade *from*
  yet; the matrix gets meaningful once v0.1 ships.

## 11. Runbook

### Create a new agent

```bash
agentforge new my-pr-reviewer --template code-reviewer
cd my-pr-reviewer
uv sync
uv run python -m my_pr_reviewer "review this PR"
```

Available templates: `minimal`, `code-reviewer`, `patch-bot`,
`docs-qa`, `triage`, `research`.

### Check what's managed by the framework

```bash
agentforge status
```

Prints files grouped by `MANAGED` (template-owned, in sync),
`FORKED` (you claimed it, upgrades skip it), `DRIFTED` (template-
owned but you edited it — next upgrade will three-way merge), and
`MISSING` (template-owned, deleted locally).

### Pull framework updates into an existing agent

```bash
agentforge upgrade --dry-run        # preview
agentforge upgrade                   # apply
agentforge upgrade --to <vcs_ref>   # pin a specific template ref
```

Copier handles the three-way merge against the answer file's
recorded template version. Files in `FORKED` state are left
untouched. The managed-files lock is refreshed afterwards.

### Claim a managed file (skip future upgrades)

```bash
agentforge fork src/myagent/agent_runtime.py
```

Strips the `AGENTFORGE-MANAGED:` marker, sets `forked=true` in the
lock. Future `agentforge upgrade` runs skip this path.

### Release a fork (re-accept framework ownership)

```bash
agentforge unfork src/myagent/agent_runtime.py
agentforge upgrade        # re-renders the template content
```

`unfork` flips the lock flag and re-prepends the marker; `upgrade`
pulls the current template content (overwriting local edits).

### Troubleshooting

- **`No .agentforge-state/answers.yml`** — the directory wasn't
  created by `agentforge new`. There is nothing to upgrade.
- **A managed file shows as `DRIFTED` after a formatter run** — the
  marker hash no longer matches. Either revert the formatting on
  that file or `fork` it to claim ownership.
- **`copier update failed`** — surfaces the underlying Copier
  exception. Most often a merge conflict in a managed file; resolve
  by hand or `fork` the file and re-run.

## 12. References

- [`scaffolding-and-upgrade.md`](../design/scaffolding-and-upgrade.md) — full design
- [`module-system.md`](../design/module-system.md) — manifest format
- [`design-principles.md`](../design/design-principles.md) — P2, P8
- ADR-0005 (Copier — Python engine)
- ADR-0021 (native TypeScript scaffolding engine)
- feat-010, feat-012
- Copier docs: https://copier.readthedocs.io/
