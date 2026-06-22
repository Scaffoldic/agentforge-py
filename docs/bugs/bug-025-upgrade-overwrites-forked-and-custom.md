---
status: open
severity: P1
found-in: 0.3.1
found-via: downstream consumer (agentforge-graph) on a real 0.2.4 → 0.3.1 upgrade
---

# bug-025 — `agentforge upgrade` overwrites forked files and erases `agentforge:custom` blocks

## Symptom

Data loss, silent on an unattended upgrade. Against template `minimal`,
framework 0.2.4 → 0.3.1:

```
$ agentforge fork AGENTS.md
  → forked AGENTS.md. Future upgrades will skip it.
$ agentforge upgrade
  → re-injected 27 shared scaffold files.
```

After the upgrade, `AGENTS.md` (and every `docs/runbooks/*.md`) is
rewritten **wholesale**: the fork is ignored and the developer-owned
`<!-- agentforge:custom -->` block — which the runbook README promises
"survives `agentforge upgrade`" — is gone. The consumer had to
hand-recover `AGENTS.md` plus three runbook custom sections.

## Reproduction

1. Scaffold an agent (`agentforge new …`).
2. Edit a managed three-section file's `agentforge:custom` block (e.g.
   `AGENTS.md`), and/or `agentforge fork <file>` and hand-edit it.
3. `agentforge upgrade`.
4. The custom block is erased; the forked file is overwritten.

## Root cause

`agentforge upgrade` refreshes files in three passes
(`cli/upgrade_cmd.py::_do_upgrade`). Passes 1–2 handle Copier-template
files and *do* honour fork status — but the **shared scaffold**
(`AGENTS.md`, `CLAUDE.md`, `.cursorrules`, copilot-instructions, the 24
runbooks) is owned by **Pass 3**, `inject_shared_scaffold`, which ran
independently of the per-file managed/forked/custom resolution:

- `cli/_shared_scaffold.py` walked `_shared/` and did
  `target.write_text(body)` **unconditionally** for every file — no
  fork check — then reset the lock entry to `forked: False`, silently
  un-forking it.
- It never preserved the custom tail. The three-section helpers
  (`split_three_section` / `merge_three_section` in `_scaffold_state.py`,
  feat-019) existed and were unit-tested, but **nothing in the upgrade
  path ever called them** — so the rendered template (managed region +
  the template's *default* custom block) replaced the file whole,
  discarding the consumer's edits.

A secondary gap: `agentforge upgrade --dry-run` printed only a one-line
summary, so none of this destruction was visible before the write.

## Fix

Route every upgrade write through fork-skip + custom-block preservation:

- New `_scaffold_state.preserve_custom_section(new_content, existing)`:
  when both the freshly rendered content and the on-disk file are
  three-section files, it keeps the **new managed region** and the
  **existing custom tail** (via `split`/`merge_three_section`). When
  either side lacks the `end-managed` marker (a plain config file, or a
  file whose markers were stripped without forking) it falls back to the
  previous whole-file write — `agentforge fork` remains the supported way
  to protect a fully hand-edited file.
- `inject_shared_scaffold` now: (a) skips any file the lock marks
  `forked`, leaving its file and lock entry untouched; (b) preserves the
  custom block on still-managed files; (c) takes a `dry_run` flag and
  returns a `SharedScaffoldResult` (`written` / `skipped_forked` /
  `preserved_custom`) instead of a bare count.
- `_do_upgrade` Pass 1 also runs `preserve_custom_section`, threads
  `dry_run` through (writing nothing), and prints a **per-file plan**
  with the action per path (`refresh` / `refresh (preserve custom block)`
  / `skip (forked)` / `add (new)` / `refresh shared …`).

## Verification

- `packages/agentforge/tests/unit/test_shared_scaffold.py` — re-injection
  skips a forked file (file + lock entry preserved); preserves a custom
  block while refreshing the managed region; `dry_run` writes neither
  file nor lock.
- `packages/agentforge/tests/unit/test_three_section_format.py` —
  `preserve_custom_section` keeps new managed + existing custom, returns
  new verbatim when there's no existing file, and falls back to whole
  overwrite when markers are absent.
- `packages/agentforge/tests/unit/test_upgrade_cmd.py` — end-to-end via
  `agentforge new` → edit custom / fork → `agentforge upgrade`: the
  custom sentinel survives, the forked file is untouched, and
  `--dry-run` writes nothing while listing per-file actions.
- `uv run pre-commit run --all-files` green.

## Notes

- Related: issue #115 (surface upgrade drift) — separate, additive.
- Closes #114.
</content>
