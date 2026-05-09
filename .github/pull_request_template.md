## Summary

<one-paragraph description of what this PR does and why>

## Tests added

- Unit: <count>
- Integration: <count>
- Conformance: <count>
- Coverage on diff: <pct>% (gate is 90%)

## Pre-commit hook output

```
✅ ruff format
✅ ruff check
✅ mypy --strict
✅ bandit -c pyproject.toml
✅ pytest unit
✅ pytest integration
✅ coverage >= 90%
```

## Checklist

- [ ] Branch follows convention: `feat/<NNN>-<slug>`, `fix/<slug>`,
      `docs/<slug>`, or `chore/<slug>`
- [ ] One feature / fix / chore — not mixed
- [ ] Conventional Commits format on every commit
      (`feat:` / `fix:` / `docs:` / `test:` / `refactor:` / `chore:` /
      `perf:` / `revert:`)
- [ ] `AGENTS.md` updated if conventions changed
- [ ] `CHANGELOG.md` entry added under `[Unreleased]`
- [ ] No `--no-verify` used (or explicit reason in commit message)
