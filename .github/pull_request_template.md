## Summary

<one-paragraph description of what this PR does and why>

## Feature

Closes feat-NNN. See `docs/features/feat-NNN-*.md` (in the design workspace).

## Design principles cited

- P<N>: <one-line how this PR honours it>
- ADR-<NNNN>: <one-line how>

## Tests added

- Unit: <count>
- Integration: <count>
- Conformance: <count>
- Coverage on diff: <pct>%

## Bugs carried (per `.claude/development-pipeline.md` §5)

- [BUG-CARRIED] feat-PRIOR: <description> — fixed in <commit-sha>

(or "None")

## Pre-commit hook output

```
✅ ruff format
✅ ruff check
✅ mypy --strict
✅ bandit
✅ pytest unit
✅ pytest integration
✅ coverage >= 90%
```

## Checklist

- [ ] Branch is `feat/NNN-slug` (one feature, one PR)
- [ ] Conventional Commits format on every commit
- [ ] Feature doc Status updated
- [ ] AGENTS.md updated if conventions changed
- [ ] ADR written if a load-bearing decision was made
- [ ] `.claude/state/current.md` reflects current state
- [ ] `.claude/state/log.md` has milestone entries for this branch
- [ ] No `--no-verify` used (or explicit user approval logged)
