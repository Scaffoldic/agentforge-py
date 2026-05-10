# Pre-commit checklist

The pre-commit hook in `.pre-commit-config.yaml` enforces this
mechanically. This file documents what it enforces, so a developer (or
AI assistant) can run the checks manually before `git commit` to fail
fast.

Run order matches the hook order. First failure stops; fix and retry.

## Code quality

- [ ] **Formatter clean** — `ruff format --check` (Py) and `biome
      format` (TS) report no changes needed.
- [ ] **Linter clean** — `ruff check` (Py) and `biome check` (TS) pass
      with zero warnings, zero errors.
- [ ] **Type checker clean** — `mypy --strict` (Py) and `tsc --noEmit`
      (TS) pass with zero errors.
- [ ] **Security linter** — `bandit -r src/` reports nothing of
      severity ≥ medium.
- [ ] **No magic numbers** — `python scripts/check_no_magic_numbers.py`
      reports clean (per `.claude/standards/configuration.md`).

## Tests

- [ ] **Unit tests** — `pytest tests/unit -q -x` passes; suite runs in
      < 30s.
- [ ] **Integration tests** — `pytest tests/integration -q -x -m "not
      live"` passes; suite runs in < 3 min.
- [ ] **Coverage** — `pytest --cov=src --cov-fail-under=90 -q` passes.
- [ ] **Coverage didn't regress** — `python
      scripts/coverage_ratchet.py` reports clean (CI-only check; local
      uses cached main coverage).

## Documentation

- [ ] **Feature doc updated** — the active `docs/features/feat-NNN-*.md`
      reflects the change (status field, examples, contracts).
- [ ] **ADR written if required** — if this commit makes a load-bearing
      decision, a new ADR is part of the commit.
- [ ] **Doc-template conformance** — `python
      scripts/check_feature_docs.py` and `scripts/check_adrs.py` pass.
- [ ] **Doc links** — `python scripts/check_doc_links.py` reports
      no broken links.
- [ ] **AGENTS.md** updated if a convention or anti-pattern changed.

## State and history

- [ ] **`.claude/state/current.md` updated** — the active state, last
      milestone, and current TODOs reflect the commit being made.
- [ ] **`.claude/state/log.md` appended** — a log entry for this
      commit's milestone.
- [ ] **`scripts/check_state_updated.py` passes** — no state staleness.

## Commit message

- [ ] **Conventional Commits format** — type, scope, subject all
      present.
- [ ] **Subject ≤ 72 chars, imperative mood, no trailing period.**
- [ ] **Body wraps at 72** if present; explains *why*.
- [ ] **References** — `Refs: feat-NNN` (and ADRs if relevant) in
      footer.
- [ ] **`Co-Authored-By:` trailer** if AI-assisted.
- [ ] **No `--no-verify`** unless explicitly user-approved and logged
      in `state/log.md`.

## Final visual check

- [ ] **`git diff --cached`** reviewed before `git commit`. No
      surprises, no secrets, no debug prints.
- [ ] **`git status`** clean except for the staged changes.

## On failure

If any check fails: do not commit. Fix the cause; re-run the failing
check; only re-run the full suite once all known issues are addressed.

If a failure is caused by an unrelated bug from a previous feature:

- Fix it on this branch (per pipeline §5).
- Add a regression test on this branch.
- Note in `state/log.md` with `[BUG-CARRIED]` prefix.
- **Do not** open a separate `bug-NNN` doc (those don't exist until
  v1.0).
