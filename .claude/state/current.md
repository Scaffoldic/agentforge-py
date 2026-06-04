---
feature: idle — v0.2.4 SHIPPED
state: idle
branch: main
started_at: 2026-06-02
last_milestone_at: 2026-06-03
last_shipped: v0.2.4 — Live-fire MCP (8-bug MCP/chat/config cluster + enh-001 HTTP server transport + bug-008). Tag v0.2.4 at merge commit 6f208e9 (PR #67); GitHub Release published; release.yml SUCCESS — all 34 packages live on PyPI at 0.2.4 in one clean run (no quota wall). Verified: TestPyPI dry run + real scaffold/upgrade end-to-end.
blocker: null
resume: "evening IST 2026-06-03 — v0.2.4 is shipped/live; nothing mid-feature. On resume: (1) MERGE PR #68 first (this state-sync PR; until then main's current.md is stale and still says 'release in flight'). (2) Then optional, non-blocking PyPI housekeeping (revoke ~/.pypirc token, Trusted Publishing, delete PYPI_PUBLISH_TRACKER.md). (3) Or start v0.3 backlog from docs/roadmap.md. No bugs open."
flags_for_user:
  - "v0.2.4 RELEASED 2026-06-03. All 34 packages live on PyPI at 0.2.4 (single clean release.yml run — first non-drip release since the quota era). GitHub Release: https://github.com/Scaffoldic/agentforge-py/releases/tag/v0.2.4"
  - "Pre-release verification done: TestPyPI dry run PASSED (34 pkgs build+upload+smoke install); real `agentforge new` + `agentforge upgrade --to 0.2.4` + fork verified end-to-end (managed refreshed, forked preserved); bug-008 confirmed in situ (answers.yml records 0.2.4)."
  - "PyPI post-drip chores STILL PENDING (housekeeping, not blocking): revoke ~/.pypirc [pypi] API token; convert the 34 projects to Trusted Publishing (release.yml already uses the gh-action publish — confirm OIDC vs token); delete PYPI_PUBLISH_TRACKER.md (drip is long complete)."
  - "Next feature work: v0.3 backlog (docs/roadmap.md). No bugs open."
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

No active feature — v0.2.4 is shipped. Next pick comes from the v0.3
backlog in `docs/roadmap.md`. Housekeeping that can be done anytime
(non-blocking): the PyPI post-drip chores (see flags above).

## Last shipped

**v0.2.4 — Live-fire MCP** (2026-06-03)

- Tag: `v0.2.4` annotated at merge commit `6f208e9` (PR #67, release prep).
- GitHub Release: <https://github.com/Scaffoldic/agentforge-py/releases/tag/v0.2.4>.
- Release notes file: `docs/releases/v0.2.4.md`.
- 34 workspace packages at `0.2.4`; **all 34 live on PyPI** — published
  in a single clean `release.yml` run (Build + Publish jobs green). First
  non-drip release since the new-project-quota era (v0.2.4 is a new
  *version* of existing projects, so the quota didn't apply).
- Theme: the 8-bug MCP/chat/config cluster from the first live
  Bedrock-backed MCP integration, plus enh-001 (MCP HTTP server transport)
  and bug-008 (scaffold version lookup). Bugs: 012 (`__` tool-name
  separator), 013 (factory auto-register), 014 + 020 (MCP runtime wiring),
  015 (vendor-SDK extra chains), 017 (tool-name charset validator), 018
  (chat session-create contract), 019 (terse config sugar).
- Pre-release verification: TestPyPI dry run PASSED (34 pkgs build +
  upload + smoke install); real `agentforge new` + `agentforge upgrade
  --to 0.2.4` + `fork` validated end-to-end (managed refreshed, forked
  preserved); bug-008 confirmed in situ.

### Previously

**v0.2.3 — Upgrade-flow fix (bug-007)** (2026-05-21) — PR #55, merge
`f6f4fba`. `agentforge upgrade` functional again (`new` persists
`answers.yml`; `upgrade` uses `run_copy` + in-place copy). 34 pkgs at
0.2.3; drip-publish completed 2026-05-28.

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
