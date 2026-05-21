---
feature: null
state: idle
branch: main
started_at: null
last_milestone_at: 2026-05-21
last_shipped: v0.2.3 — Upgrade-flow fix (bug-007) — PR #55 merged 2026-05-21; tag v0.2.3 pushed; GitHub Release published. 8 of 34 packages live on PyPI.
blocker: null
flags_for_user:
  - "26 of 34 packages still pending PyPI publish at v0.2.3 (blocked by daily new-project quota). Run `gh workflow run release.yml --ref v0.2.3` once per day until they all land, or until admin@pypi.org grants the quota-increase request."
  - "v0.2.2 git tag is local-only (intentional — v0.2.3 supersedes). If a complete GitHub Releases history matters, push `git push origin v0.2.2` + `gh release create v0.2.2 --notes-file docs/releases/v0.2.2.md`. Note: pushing the tag triggers another `release.yml` run that burns a daily quota window without landing anything new."
  - "PR #56 (docs only — bug-008 + pre-release tag callout) is open and ready to merge."
  - "bug-008 queued for v0.2.4: `_template_version()` renders `0.0.0+unknown` because `importlib.metadata.version()` looks up the import name (`agentforge`) instead of the PyPI distribution name (`agentforge-py`). Cosmetic — affects marker headers and answers.yml, not functionality."
  - "Production PyPI token still sitting in `~/.pypirc [pypi]` (one-time rescue path from 2026-05-20). Should be revoked on PyPI's web UI when convenient."
---

## Active feature

**None.** v0.2.3 shipped 2026-05-21. Pick the next item when
ready — either drip the 26 pending packages, land bug-008 →
v0.2.4, or move to the v0.3 backlog.

## Last shipped

**v0.2.3 — Upgrade-flow fix (bug-007)** (2026-05-21)

- Merge commit: `f6f4fba` (PR #55).
- Tag: `v0.2.3` annotated at the merge commit.
- GitHub Release: <https://github.com/Scaffoldic/agentforge-py/releases/tag/v0.2.3>.
- Release notes file: `docs/releases/v0.2.3.md`.
- 34 workspace packages at `0.2.3`; **8 of those live on PyPI**
  (`agentforge-core`, `-py`, `-anthropic`, `-bedrock`, `-chat`,
  `-a2a`, `-memory-sqlite`, `-testing`).
- Theme: `agentforge upgrade` is functional again. Bug-007
  was a P0 in two parts — `agentforge new` didn't persist
  `answers.yml`, and `agentforge upgrade` delegated to Copier's
  `run_update` which requires VCS-versioned templates. v0.2.3
  fixes both — `new` writes the file itself; `upgrade` uses
  `run_copy` against a temp dir then copies non-forked managed
  files in place. End-to-end validated against
  `agents/code-reviewer/`.

### Previously this session (2026-05-21)

- **v0.2.2 — Scaffold validation fixes (PR #53 + #54).** Six
  framework bugs found by first-scaffolding `code-reviewer`
  against published v0.2.1 — provider extra missing,
  `agent.strategy` missing, no console script, `.env` not
  loaded, stale "feat-002 ships" error, import vs distribution
  name confusion. All fixed with a regression test that locks
  in the scaffold contract.

### Previously

- v0.2.1 — Publishable. PR #50 + #51 merged 2026-05-20; tag
  v0.2.1 pushed. First 4 of 34 packages live on PyPI under the
  new `agentforge-py` distribution name; 30 blocked by the
  hidden PyPI new-project quota at the time.
- v0.2.0 — Drivers. PR #49 merged 2026-05-15. Every locked v0.1
  ABC got a working driver; 16 new sister packages introduced.

## Next pick candidates

**Path 1 — Drip the 26 remaining packages to v0.2.3 on PyPI.**

```bash
gh workflow run release.yml --ref v0.2.3
```

Re-run daily until all 34 land. Each daily window ships ~4 new
projects before hitting the quota wall. `skip-existing: true` on
`pypa/gh-action-pypi-publish` keeps the run idempotent.

**Path 2 — Land bug-008 + cut v0.2.4.**

`docs/bugs/bug-008-*.md` describes the fix: `version("agentforge")`
→ `version("agentforge-py")` in two call sites
(`new_cmd._template_version`, `_shared_scaffold._framework_version`).
~5 lines + a regression test. Bump version, manual upload for
the 8.

**Path 3 — v0.3 backlog.**

From `docs/roadmap.md`:

- `down` migrations / schema rollback (feat-024 v0.3+).
- Native single-Cypher / SurrealQL graph-augmented retrieval
  inside Neo4j / SurrealDB (feat-023 sister-package follow-up).
- Multi-cluster Redlock for `RedisSessionLock` (feat-020 v0.3+).
- True streaming-aware `stream-then-redact` (feat-020 v0.3+).
- Evidently real-time drift dashboards via Cloud (feat-009 v0.3+).
- Optional eval sister packages (`-ragas` / `-deepeval` /
  `-toxicity` / `-codeexec`).
- TypeScript port of the v0.2 surface (target: v0.4).

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `.claude/state/log.md` — the latest entry covers today's three releases + the pipeline-rule update
5. `docs/roadmap.md` to pick next feature
