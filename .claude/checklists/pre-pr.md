# Pre-PR checklist

Before `gh pr create`, verify the branch is in PR-ready state.

## Branch state

- [ ] All commits on the branch follow Conventional Commits.
- [ ] `git rebase origin/main` applied — no merge commits, linear
      history.
- [ ] No unrelated changes — every commit relates to the active feature.
- [ ] Branch pushed to origin: `git push -u origin feat/NNN-slug`.

## Pre-commit ran on every commit

- [ ] Each commit has the hook's checks passing. (If you used
      `--no-verify` anywhere, surface it now and fix.)

## Cleanliness

- [ ] No stray `print()`, `console.log()`, debug code.
- [ ] No `TODO` / `FIXME` comments without an owner and an issue
      reference. (We don't open issues for bugs in v0.x — instead, the
      TODO must reference a future feature or a `state/log.md` entry.)
- [ ] No commented-out code.
- [ ] No new dependencies without an entry in the relevant
      `pyproject.toml` / `package.json` and a justification in the
      feature doc.

## Tests pass on a fresh checkout

- [ ] `git clean -fdx && uv sync && pytest -q` succeeds (or TS
      equivalent). Verifies no local-state contamination.
- [ ] Live tests intentionally not run (they go through scheduled CI).

## Documentation complete

- [ ] Feature doc Status updated (`in-progress` → ready for `shipped`
      pending merge).
- [ ] AGENTS.md updated if conventions changed.
- [ ] `## Runbook` section added/updated on the matching canonical
      spec (task-oriented, audience: agent developers using the
      framework).
- [ ] **Forward references swept.** Run
      `git grep -nE 'feat-NNN|<backlog-pkg-names>' docs/features/*.md`
      for this feature's number and any backlog packages it ships.
      Update or delete every match in existing `## Runbook` sections
      so they reflect the shipped surface, not past-tense "when this
      lands…" caveats.
- [ ] ADR(s) written for any load-bearing decisions.
- [ ] Cross-references resolve (no dangling links).

## State files

- [ ] `.claude/state/current.md` reflects `state: pre-commit` or
      `state: committed` going into the PR.
- [ ] `.claude/state/log.md` has entries for every milestone on this
      branch (start, design approval, implementation done, tests done,
      ready for PR).

## PR body

- [ ] **Summary** — one paragraph describing what this PR does.
- [ ] **Feature reference** — `Closes feat-NNN.` with link to the
      feature doc.
- [ ] **Design principles cited** — which P# from the 12 principles,
      which ADRs.
- [ ] **Test counts** — unit, integration, conformance.
- [ ] **Coverage on diff** — percentage; must be ≥ 90%.
- [ ] **Bugs carried** — list of `[BUG-CARRIED]` items from
      `state/log.md`, with the commit that fixed each. Or "None".
- [ ] **Pre-commit output** — confirm `✅ all green`.

## PR title

- [ ] **`feat-NNN: <feature title>`** — exact format. The squashed
      merge commit will use this verbatim.

## Self-review

- [ ] **`gh pr view --web`** opened the PR in the browser; the diff was
      visually reviewed by the author one more time.
- [ ] **CI status** — the first CI run is green (wait for it; don't
      ask reviewers until CI is green).

## After raising

- [ ] Updated `.claude/state/current.md`: `state: pr-raised`.
- [ ] Appended PR URL to `.claude/state/log.md`.
- [ ] If user is available, ping for review.
