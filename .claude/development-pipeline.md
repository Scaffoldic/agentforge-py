# Development Pipeline

The per-feature workflow, end to end. Every feature follows this exactly.
Deviations require user approval and a note in `.claude/state/log.md`.

---

## 0. Lifecycle states

A feature moves through these states. The current state for the active
feature is recorded in `.claude/state/current.md`.

```
  proposed → analysing → designing → implementing → testing
            → pre-commit → committed → pushed → pr-raised → merged → shipped
```

`shipped` means the feature doc has its `Status: shipped` metadata field
set and the version is recorded in the doc.

---

## 1. Stage: pick the next feature

**Trigger:** the previous feature is `shipped` (merged + main pulled).
**Source of truth:** `docs/features/README.md` catalogue.

Steps:

1. Read `docs/features/README.md`. Pick the lowest-numbered feature with
   status `proposed` whose dependencies are all `shipped`.
2. If multiple are eligible, pick by the **0.1 critical-path order** in
   the catalogue, then by feature number ascending.
3. If none are eligible (all dependencies blocked), surface it; do not
   work around the blocker.
4. Update `.claude/state/current.md`:
   - `feature: feat-NNN-slug`
   - `state: analysing`
   - `started_at: <YYYY-MM-DDTHH:MM>`
   - `branch: feat/NNN-slug` *(not yet created — see stage 2)*

---

## 2. Stage: create the branch

```bash
git checkout main
git pull --ff-only
git checkout -b feat/NNN-slug
```

Branch naming is locked: `feat/NNN-slug` (lowercase, hyphenated). The
`NNN` is the feature number; `slug` is the feature title slug from its
filename.

Update `state/current.md` with the branch name. Append to `state/log.md`:

```
## YYYY-MM-DD — feat-NNN started
Branch: feat/NNN-slug
```

---

## 3. Stage: analyse

**Goal:** read everything required to understand the feature.

Mandatory reads, in order:

1. The feature doc itself: `docs/features/feat-NNN-*.md` end-to-end.
2. Every linked design doc (in §10 References).
3. Every linked ADR.
4. Every dependency feature's doc (`Depends on:` field in metadata).
5. The existing code (if any) for the area the feature touches.

Capture in `state/current.md` under `analysis_notes:`:

- What contracts are being added or extended?
- What modules are affected?
- What existing tests need updating?
- What new files need creating (with proposed paths)?
- What config keys are added / changed?
- Any ambiguities in the feature doc — surface them BEFORE implementing.

Update `state/current.md`: `state: designing`.

---

## 4. Stage: design

**Goal:** lock the implementation approach before writing code.

Outputs:

- A short design note in `state/current.md > design_notes:` covering:
  - File layout — exactly which files will be created/modified
  - Public API surface (signatures, no bodies) for the new ABCs/classes
  - Test plan — unit tests to write, integration tests to write,
    conformance tests to add or update, fixtures needed
  - Configuration keys + their defaults + Pydantic/Zod schema sketch
  - Migration impact (if any) — only relevant for memory drivers

If the design forces an architectural decision (e.g. "should this be a
new ABC or extend an existing one?"), **write a new ADR** before
proceeding. New ADRs land on the same feature branch.

If the user is available, present the design and wait for approval. If
working unattended (e.g. autonomous mode), proceed but flag in
`state/current.md > flags_for_user:` so the user can review on next
session resume.

Update `state/current.md`: `state: implementing`.

---

## 5. Stage: implement

Rules:

- **Configuration over hardcoding.** Every threshold, path, timeout,
  size goes through config (per `.claude/standards/configuration.md`).
- **Type hints everywhere.** Strict `mypy` / `tsc` from line one.
- **Async by default** for any I/O-touching code (per ADR-0014).
- **One commit per coherent unit of work.** Not "WIP commits"; each
  commit must build and tests must pass.
- **Update docs in the same commit as code.** Feature doc status,
  AGENTS.md (if conventions change), runbook entries.

If you find a bug in code from a previous feature:

- Fix it on **this** branch.
- Add a regression test on **this** branch.
- Note it in `state/log.md` under the active feature with prefix
  `[BUG-CARRIED] feat-PRIOR: <description>`.
- **Do not** create a `docs/bugs/bug-NNN-*.md` — those don't exist
  until v1.0.

Update `state/current.md`: `state: testing` once code is written.

---

## 6. Stage: test

Three test classes, all required:

1. **Unit tests** — per public function/method. `tests/unit/`.
2. **Integration tests** — cross-module interactions. `tests/integration/`.
3. **Conformance tests** — if the feature defines an ABC, every shipped
   driver runs the same suite. `tests/conformance/`.

Coverage gate: **≥ 90%** on the diff. Pre-commit blocks below.

Test data: in YAML / JSON fixtures under `tests/fixtures/`. **No
hardcoded test inputs** — `.claude/standards/configuration.md` covers the
rule.

Live tests (those that hit a real provider) are marked `@pytest.mark.live`
and are excluded from the pre-commit run; they run in CI on a separate
schedule.

Update `state/current.md`: `state: pre-commit`.

---

## 7. Stage: pre-commit

The pre-commit hook (`.pre-commit-config.yaml`) runs:

- `ruff format` + `ruff check --fix`
- `mypy --strict`
- `pytest tests/unit -q -x`
- `pytest tests/integration -q -x -m "not live"`
- `pytest --cov --cov-fail-under=90`
- Doc-template conformance (`scripts/check_feature_docs.py`)
- ADR numbering (`scripts/check_adrs.py`)
- State currency (`scripts/check_state_updated.py`)
- Conventional Commits message format

On red: fix the failure. **Never** bypass with `--no-verify` unless the
user explicitly authorises it for a specific commit (and that
authorisation is logged in `state/log.md`).

On green: proceed to commit.

Update `state/current.md`: `state: committed`.

---

## 8. Stage: commit and push

Conventional Commits format:

```
<type>(<scope>): <subject>

<body — optional, wrap at 72>

<footer — optional: refs, breaking changes>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`. Scope is the
feature id or area: `feat(feat-001)`, `docs(adr-0021)`, `chore(ci)`.

Commands:

```bash
git push -u origin feat/NNN-slug
gh pr create --title "feat-NNN: <title>" --body "<see template>"
```

Update `state/current.md`: `state: pushed`, then `state: pr-raised`.
Append PR URL to `state/log.md`.

---

## 9. Stage: PR review and merge

PR template (auto-loaded from `.github/pull_request_template.md` once
that file lands; for now use this body):

```markdown
## Summary
<one-paragraph description>

## Feature
Closes feat-NNN. See [docs/features/feat-NNN-*.md](...).

## Design principles cited
- P<N>: <one-line how>
- ADR-<NNNN>: <one-line how>

## Tests added
- Unit: <count>
- Integration: <count>
- Conformance: <count>
- Coverage on diff: <pct>%

## Bugs carried (per .claude/development-pipeline.md §5)
- [BUG-CARRIED] feat-PRIOR: <description> — fixed in <commit>
(or "None")

## Pre-commit hook output
✅ all green
```

On approval + merge to main:

1. Switch to main, pull.
2. Mark feature `Status: shipped` in `docs/features/feat-NNN-*.md`.
3. Mark feature `shipped` in `docs/features/README.md` catalogue.
4. Append to `state/log.md`: `feat-NNN shipped at <commit-sha>`.
5. Reset `state/current.md` to `state: idle` until next feature picked.

Update `state/current.md`: `state: shipped`, then `state: idle`.

---

## 10. The bug rule (during v0.x)

**No `docs/bugs/*` or `docs/enhancements/*` entries are written during
v0.x development.** Every defect found mid-feature is fixed on the
active feature branch and tracked under that feature's progress in
`state/log.md`.

The bug-tracking documents (`bug-NNN-*.md` and `enh-NNN-*.md`) come
into existence the moment we cut **v1.0**. From then on, defects
against shipped v1.0 features become first-class `bug-NNN` docs;
improvements become `enh-NNN` docs. Until then, the cleanest path is
to keep all work flowing through the feature lane.

Why: until v1.0, the framework is still under design. Calling something
a "bug" implies a stable contract was violated; we don't have stable
contracts yet, so labelling things "bug" vs "feature change" is noise.

---

## 11. Stage transitions cheat sheet

| From | Trigger | To |
|---|---|---|
| `idle` | Pick next feature | `analysing` |
| `analysing` | All required reading done | `designing` |
| `designing` | Design approved (or recorded for review) | `implementing` |
| `implementing` | Code complete on branch | `testing` |
| `testing` | All test classes written | `pre-commit` |
| `pre-commit` | Hook green | `committed` |
| `committed` | Pushed to origin | `pushed` |
| `pushed` | PR raised | `pr-raised` |
| `pr-raised` | Merged to main | `shipped` |
| `shipped` | Cleanup done | `idle` |

A failure or blocker at any stage moves to `blocked` with a reason in
`state/current.md > blocker:`.

---

## 12. References

- [`AGENTS.md`](../AGENTS.md) — top-level rules
- [`.claude/standards/`](./standards/) — every standard cited above
- [`.claude/checklists/`](./checklists/) — concrete actionable checklists per stage
- [`.claude/state/`](./state/) — current state + log
- [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) — hook implementation
