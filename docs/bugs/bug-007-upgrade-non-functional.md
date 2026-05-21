---
status: open
severity: P0
found-in: v0.2.2
found-via: scaffold-upgrade validation, 2026-05-21
---

# bug-007 — `agentforge upgrade` is non-functional

## Symptom

The `agentforge upgrade` command always fails in v0.2.x:

```bash
$ agentforge upgrade --to 0.2.2
No .agentforge-state/answers.yml; this directory wasn't scaffolded
by `agentforge new`. Nothing to upgrade.
```

Even on agents that *were* scaffolded by `agentforge new`. Even if
the user hand-writes `.agentforge-state/answers.yml`, the second
failure mode is:

```bash
$ agentforge upgrade --to 0.2.2
upgrade failed: copier update failed: Template not found
```

The command is documented as the migration path in the
README, the `agentforge upgrade --help` output, the per-template
scaffold READMEs, and the runbook
`docs/runbooks/15-upgrade-your-agent.md`. None of them work today.

## Reproduction

```bash
agentforge new my-agent --template minimal --provider anthropic --no-prompts
cd my-agent
ls .agentforge-state/                    # → only managed-files.lock, no answers.yml
agentforge upgrade                       # → "Nothing to upgrade"

# Hand-write answers.yml with minimum fields:
cat > .agentforge-state/answers.yml <<EOF
_commit: HEAD
_src_path: $(python -c "from importlib import resources; print(resources.files('agentforge.templates').joinpath('minimal'))")
project_slug: my-agent
llm_provider: anthropic
EOF

agentforge upgrade --to 0.2.2            # → "copier update failed: Template not found"
```

## Root cause

Two related problems, one architectural:

### Part A — `agentforge new` does not write `answers.yml`

`packages/agentforge/src/agentforge/cli/new_cmd.py:_run_new` calls
`_run_copier` which invokes Copier's `run_copy`. Copier's
`_answers_file` directive in each template's `copier.yml`
(`_answers_file: ".agentforge-state/answers.yml"`) should cause
Copier to write the resolved answers to that path. Empirically it
does not, across multiple fresh scaffolds with
`--no-prompts`.

Even if Copier *did* write it reliably, the file would not be
sufficient for `agentforge upgrade` because of Part B.

### Part B — Copier's `run_update` requires a VCS-versioned template

`packages/agentforge/src/agentforge/cli/upgrade_cmd.py:_run_copier_update`
delegates to Copier's `run_update`. `run_update` performs a
three-way merge by:

1. Reading the recorded `_src_path` and `_commit` from
   `answers.yml`.
2. Doing a VCS checkout of the template at the recorded commit
   (the "old" version).
3. Doing a VCS checkout at the new version (`vcs_ref`).
4. Three-way merging the diff into the destination.

AgentForge ships templates **inside** the framework package at
`packages/agentforge/src/agentforge/templates/<name>/`, not as a
separate Copier-compatible git repo. The in-package directory is
not VCS-traversable as a standalone template repository — Copier
can't `git fetch` it at a specific ref because the templates
aren't versioned at the granularity Copier expects.

This is explicitly flagged in `new_cmd.py:4-7`:

> *feat-011 ships six templates inside `agentforge/templates/<name>/`
> (see Implementation status §4.4 — local templates instead of the
> spec's separate-repo design; migration to `agentforge-templates`
> is a 0.4+ follow-up).*

So the in-package decision (v0.2 compromise) broke the upgrade
path. The deferred `agentforge-templates` repo migration would
fix Part B properly.

## Fix

Two-part fix landing in v0.2.3:

### Part A — Write `answers.yml` ourselves in `_run_new`

After `_run_copier`, write the resolved Copier answers to
`.agentforge-state/answers.yml`. Include `_template_name` and the
four template variables (`project_name`, `project_slug`,
`llm_provider`, `description`) so the file is sufficient for
later upgrade.

### Part B — Replace `copier update` with a custom in-package upgrade

In `upgrade_cmd.py:_run_upgrade`, drop the dependency on Copier's
`run_update`. Instead:

1. Read the saved answers.
2. Resolve the template name → its filesystem path inside the
   current framework install (via `importlib.resources` — same
   helper as `agentforge new`).
3. Render the template into a temp directory using the same
   `run_copy` we use for fresh scaffolds.
4. For each entry in the existing `managed-files.lock`:
   - If forked → leave alone.
   - Else → overwrite the file in-place from the temp render and
     refresh the hash.
5. For any file in the temp render that's *not* in the existing
   lock → add it (new managed file introduced by the upgrade).
6. Re-inject the shared scaffold (`_shared/` — runbooks +
   AI-assistant rules) with the new framework version.
7. Write the refreshed lock.

This bypasses Copier's VCS requirement entirely. The trade-off:
no three-way merge for managed files (a user-edited managed file
is overwritten on upgrade — that's why we have `agentforge fork`).
This matches the actual on-disk contract: managed files are
framework-owned, custom edits should be in
`<!-- agentforge:custom -->` blocks or in forked files.

## Verification

```bash
# Fresh scaffold writes answers.yml.
agentforge new test-agent --template minimal --provider anthropic --no-prompts
cat test-agent/.agentforge-state/answers.yml         # should exist + have _template_name

# Upgrade actually runs.
cd test-agent
agentforge upgrade --to 0.2.3                        # should succeed
# Verify managed files got refreshed:
diff <(agentforge status) <(...)                     # all "managed", no "drifted"
```

Add regression tests in `packages/agentforge/tests/unit/test_upgrade_cmd.py`:

- `test_new_writes_answers_yml` — `agentforge new` persists
  `_template_name` + the four template variables.
- `test_upgrade_refreshes_managed_files` — scaffold an agent,
  modify a managed-file template variable, run upgrade, assert
  the change propagated.
- `test_upgrade_preserves_forked_files` — fork a file, run
  upgrade, assert the forked file's contents are untouched.

## Why this matters

`agentforge upgrade` is the **only** advertised migration path
between AgentForge versions. Without it:

- Users on v0.2.1 can't pull the bug-001–006 fixes into their
  existing scaffolds without deleting and re-scaffolding (losing
  any local code).
- The "AGENTFORGE-MANAGED + AGENTFORGE-FORKED" file-ownership
  contract is meaningless if upgrades can't actually refresh
  managed files.
- The 21 shipped runbooks promise an upgrade path that doesn't
  exist.

The in-package fix is intentionally a v0.2.x band-aid. The
spec-aligned solution — `agentforge-templates` as a separate
versioned repo + restoring Copier's three-way merge — remains a
v0.4 target.

Related: [[v0-2-1-pypi-publish-in-flight]].
