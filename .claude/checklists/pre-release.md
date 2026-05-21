# Pre-release checklist

Run this checklist top-to-bottom before pushing a `vX.Y.Z` git
tag and publishing the GitHub Release. Coordinated release train
per ADR-0015 — every workspace package bumps to the same minor
in lockstep.

## 1. Branch + state

- [ ] On `main`. Clean working tree (`git status`).
- [ ] Synced with `origin/main` (`git pull --ff-only`).
- [ ] Every feature PR for the target minor is merged. Open PRs
      either ship in this train or move to the next.

## 2. Version bump

- [ ] Every member of `[tool.uv.workspace.members]` has its
      `pyproject.toml` `[project] version` bumped to `X.Y.Z`.
- [ ] Root `pyproject.toml` (if it carries a version) is bumped.
- [ ] No pinned dep on `agentforge-core` (or any in-train
      package) is left at an earlier minor.

```bash
# One-shot check:
rg -n '^version = "' packages/*/pyproject.toml
```

## 3. Gate

- [ ] `uv sync` succeeds against the bumped versions.
- [ ] `uv run pre-commit run --all-files` is green
      (ruff format + ruff check + mypy --strict + bandit +
      pytest + ≥90 % coverage).
- [ ] CI on `main` is green for the commit being tagged.

## 4. CHANGELOG

- [ ] `CHANGELOG.md`'s `[Unreleased]` section has every notable
      change since the last tag. (Per Keep a Changelog v1.1
      under `Added` / `Changed` / `Deprecated` / `Removed` /
      `Fixed` / `Security`.)
- [ ] Rename `## [Unreleased]` → `## [X.Y.Z] — YYYY-MM-DD`.
- [ ] Append a fresh empty `## [Unreleased]` section above it
      for the next cycle.
- [ ] Each entry references the canonical spec
      (`docs/features/feat-NNN-*.md`) or ADR where applicable.

## 5. Release notes

- [ ] Copy `.claude/templates/release-notes.md` to
      `docs/releases/vX.Y.Z.md`.
- [ ] Fill **every** section. Highlights, breaking changes,
      coordinated release train table, cross-language status,
      shipped features, acknowledgements. The template's
      comments call out what each section needs.
- [ ] No placeholder text (`<feature title>`, `<…>`, etc.)
      remains.
- [ ] Migration guide present when there is any breaking change;
      "**None**" written out when there isn't.

## 6. Docs sync

- [ ] `docs/features/README.md` — every feature shipped in this
      train shows `shipped` (not `proposed`).
- [ ] Each shipped spec's metadata Status field reads
      `shipped (Python — <surface>)` (or equivalent).
- [ ] `docs/roadmap.md` Shipped table lists the new release row;
      Backlog reflects what slid to the next train.
- [ ] `README.md` install snippets pin the new version (if they
      pin at all).

## 7. State

- [ ] `.claude/state/current.md` `last_shipped` updated.
- [ ] `.claude/state/log.md` has a `## YYYY-MM-DDTHH:MM —
      vX.Y.Z released` entry summarising what landed.

## 8. TestPyPI dry run (**MANDATORY** — gate before pushing the production tag)

> Burns no production-PyPI version number, catches almost every
> failure mode (bad metadata, missing files, bad pins, name
> typos) cheaply. PyPI does **not** allow re-uploads of the same
> version, so a broken first attempt at production forces a
> `.postN` bump. Don't skip this.

**One command** drives the whole flow — see
[`scripts/testpypi_dry_run.py`](../../scripts/testpypi_dry_run.py):

```bash
python scripts/testpypi_dry_run.py
```

It builds all 34 packages, uploads to TestPyPI in
rate-limit-aware batches (TestPyPI is aggressive — solo
`twine upload dist/*` will 429), smoke-installs `agentforge-py`
from TestPyPI, and imports the runtime. Exits non-zero on any
failure. Detail in
[`playbooks/publish-to-pypi.md`](../../playbooks/publish-to-pypi.md) §3.

- [ ] Every wheel + sdist (68 artefacts) uploaded to TestPyPI
      without metadata errors.
- [ ] `pip install agentforge-py[<extra>]==X.Y.Z` from TestPyPI
      succeeds in a fresh venv.
- [ ] `from agentforge import Agent` imports cleanly.
- [ ] At least one sister-package category smoke-tested
      (provider / memory / chat / reranker / observability /
      guardrail).

**Block on red.** Fix any failure, rebuild, re-upload to
TestPyPI under the same (or a `.devN`-bumped) version, and rerun
the smoke install. Only proceed to §9 when all four boxes are
ticked.

## 9. Tag + publish

- [ ] `git tag -a vX.Y.Z -m "AgentForge vX.Y.Z — <codename>"`.
- [ ] `git push origin vX.Y.Z`.
- [ ] `gh release create vX.Y.Z --notes-file docs/releases/vX.Y.Z.md`.
- [ ] Verify the GitHub Release page renders the notes
      correctly; attach any binary artefacts if applicable.

> **Do NOT skip the tag + GitHub Release step even when PyPI
> publishing is partial.** A common temptation when the
> new-project quota (see
> [`feedback_pypi_new_project_quota`](../../../.claude/projects/...))
> means only a subset of the 34 packages can publish: skip
> tagging so `release.yml` doesn't fire and 429 on the
> unpublished ones. **Wrong.** `release.yml` is idempotent
> (`skip-existing: true` on `pypa/gh-action-pypi-publish`); a
> partial publish leaves no broken state and re-runs cleanly via
> `gh workflow run release.yml --ref vX.Y.Z` once the quota
> window resets. **Always tag**, always create the GitHub
> Release. Skipping cascades into:
>
> - Missing GitHub Releases page for the version.
> - No `git log vX.Y.0..vX.Y.Z` diff view between releases.
> - `last_shipped` in `.claude/state/current.md` drifts away
>   from PyPI reality.
> - Future contributors can't reproduce which commit shipped
>   what bytes to PyPI.
>
> Manually-uploaded wheels live on PyPI forever once uploaded;
> the git tag is the only durable record of "commit X became
> version Y". Bug-007 retro (v0.2.2/v0.2.3, 2026-05-21) shipped
> *manually* without tags for two releases — recovery required
> back-dating tags after the fact, which loses the trigger-an-on-time-release.yml-run benefit.

## 10. Post-release

- [ ] PyPI: each workspace package built and uploaded
      (`uv build` + `twine upload` per package; or the
      automation that will replace this once CI publishing
      lands).
- [ ] Announcement drafted (README / discussions / blog).
- [ ] Bump the `[Unreleased]` section of CHANGELOG.md back to
      empty for the next cycle (covered in §4 — verify).
- [ ] Open a `chore/post-release-cleanup` PR if any drift was
      surfaced during the train (rare but possible).

---

## Cadence reference

Per ADR-0015:

- During 0.x — release train every 2 weeks.
- Patch releases (0.x.y → 0.x.(y+1)) between trains are bug
  fixes only.
- Breaking changes ship at minor bumps and **require** a
  migration guide in the release notes.

## References

- [`.claude/templates/release-notes.md`](../templates/release-notes.md)
- [`.claude/standards/git.md`](../standards/git.md) §Tagging &
  releases
- [ADR-0015 — Coordinated release train](../../docs/adr/0015-coordinated-release-train.md)
- [Keep a Changelog v1.1](https://keepachangelog.com/en/1.1.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
