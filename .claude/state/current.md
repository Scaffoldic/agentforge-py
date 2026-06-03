---
feature: v0.2.4 release — cut the train (cluster complete)
state: pr-raised
branch: chore/release-v0.2.4
started_at: 2026-06-02
last_milestone_at: 2026-06-03
last_shipped: v0.2.3 — Upgrade-flow fix (bug-007), PR #55 merged 2026-05-21; tag + GitHub Release published. ALL 34 packages live on PyPI at v0.2.3. v0.2.4 cluster fully merged to main (all 8 bugs + enh-001 + bug-008); release in flight (NOT yet tagged).
blocker: null
resume: null
flags_for_user:
  - "PR #67 OPEN (chore/release-v0.2.4): release prep — CHANGELOG `[0.2.4]` dated 2026-06-03; docs/releases/v0.2.4.md written; state synced. Reversible in-repo prep only. https://github.com/Scaffoldic/agentforge-py/pull/67 — awaiting merge."
  - "v0.2.4 CLUSTER COMPLETE on main: #59 (bug-020+014), #60 (bug-012), #61 (bug-017), #62 (bug-015), #63 (bug-019), #64 (bug-018), #65 (bug-013), #66 (enh-001 + bug-008, merge 325e98f). 34 pkgs at 0.2.4."
  - "IRREVERSIBLE STEPS NEED USER (paused here): (1) pre-release checklist §8 MANDATORY TestPyPI dry run (`python scripts/testpypi_dry_run.py`) — needs TestPyPI creds. (2) After #67 merges + dry-run green: tag `v0.2.4` at the merge commit, `gh release create v0.2.4 --notes-file docs/releases/v0.2.4.md`; the tag triggers release.yml which publishes 34 packages to PyPI (immutable). v0.2.4 is a NEW VERSION of existing projects, so the new-project quota does NOT apply — all 34 can publish."
  - "PyPI post-drip chores still pending: revoke ~/.pypirc [pypi] token; convert to Trusted Publishing; delete PYPI_PUBLISH_TRACKER.md."
  - "bug-008 still queued for v0.2.4 (NOT done): version(\"agentforge\")→version(\"agentforge-py\") in cli/new_cmd.py + cli/_shared_scaffold.py. ~5 lines."
  - "v0.2.4 CHANGELOG header is `## [0.2.4] — unreleased`; set the date + tag only after the whole cluster lands."
  - "PyPI v0.2.3 drip COMPLETE (34/34). Post-completion chores: revoke ~/.pypirc [pypi] token; convert projects to Trusted Publishing; delete PYPI_PUBLISH_TRACKER.md (see that file + memory)."
---

## Active feature

**v0.2.4 — Live-fire MCP.** Eight framework defects + one enhancement
from the first live Bedrock-backed MCP integration. **All merged to
main** (34 pkgs at 0.2.4):

| PR | What |
|---|---|
| #59 | bug-020 + bug-014 — MCP runtime wiring (the unblocker) |
| #60 | bug-012 — MCP tool-name `.`→`__` separator |
| #61 | bug-017 — provider tool-name charset validator |
| #62 | bug-015 — meta-package vendor-SDK extra chains |
| #63 | bug-019 — terse evaluator/guardrail config sugar |
| #64 | bug-018 — chat session-create contract |
| #65 | bug-013 — MCPServer factories auto-register tools |
| #66 | enh-001 (MCP HTTP server transport) + bug-008 (version lookup) |

Release prep is **PR #67** (`chore/release-v0.2.4`): CHANGELOG `[0.2.4]`
dated 2026-06-03, `docs/releases/v0.2.4.md` written, state synced.
Reversible in-repo prep only.

## Pickup on resume — finish cutting v0.2.4

1. **Merge PR #67** (release prep).
2. **§8 TestPyPI dry run (MANDATORY, needs user creds):**
   `python scripts/testpypi_dry_run.py` — builds 34 pkgs, uploads to
   TestPyPI, smoke-installs `agentforge-py==0.2.4`. Block on red.
3. **Tag + publish** (irreversible — confirm before running):
   - Pull main. `git tag -a v0.2.4 -m "AgentForge v0.2.4 — Live-fire MCP"`
     at the #67 merge commit; `git push origin v0.2.4`.
   - `gh release create v0.2.4 --notes-file docs/releases/v0.2.4.md`.
   - The tag triggers `release.yml` → publishes 34 pkgs to PyPI.
     v0.2.4 is a NEW VERSION of existing projects → the new-project
     quota does NOT apply; all 34 publish. `skip-existing` keeps it
     idempotent (re-run `gh workflow run release.yml --ref v0.2.4`).
4. **After release:** set `last_shipped` to v0.2.4 + log `released`
   entry; PyPI post-drip chores (revoke `~/.pypirc [pypi]` token,
   Trusted Publishing, delete `PYPI_PUBLISH_TRACKER.md`).

## Last shipped

**v0.2.3 — Upgrade-flow fix (bug-007)** (2026-05-21)

- Merge commit: `f6f4fba` (PR #55).
- Tag: `v0.2.3` annotated at the merge commit.
- GitHub Release: <https://github.com/Scaffoldic/agentforge-py/releases/tag/v0.2.3>.
- Release notes file: `docs/releases/v0.2.3.md`.
- 34 workspace packages at `0.2.3`; **ALL 34 now live on PyPI**
  (drip-publish completed 2026-05-28 — phoenix + statsd were the
  final two; see `PYPI_PUBLISH_TRACKER.md`).
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
