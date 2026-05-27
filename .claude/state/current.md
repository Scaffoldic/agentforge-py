---
feature: bug-009 (ReAct + provider clients must round-trip tool_calls)
state: in-progress
branch: fix/bug-009-react-loop-drops-tool-calls
started_at: 2026-05-27
last_milestone_at: 2026-05-27
last_shipped: v0.2.3 — Upgrade-flow fix (bug-007) — PR #55 merged 2026-05-21; tag v0.2.3 pushed; GitHub Release published. 32 of 34 packages live on PyPI (presidio/nemo/llamaguard/evidently added 2026-05-27; phoenix + statsd remain).
blocker: null
flags_for_user:
  - "32 of 34 packages live on PyPI at v0.2.3 (phoenix + statsd pending — final drip window 2026-05-28)."
  - "bug-009 in flight: P0 reported by a downstream consumer 2026-05-27. ReAct drops response.tool_calls when re-feeding assistant turns; Bedrock Converse rejects every tool-using prompt on iteration 2. Fix touches core + ReAct + bedrock/openai/anthropic clients; targets v0.2.4."
  - "bug-008 also queued for v0.2.4: `version(\"agentforge\")` should be `version(\"agentforge-py\")` in cli/new_cmd.py and cli/_shared_scaffold.py. ~5 lines. Could fold into the v0.2.4 train or ship in a separate PR."
  - "v0.2.2 git tag is local-only (intentional — v0.2.3 supersedes). Pushing it burns a quota window without landing anything new."
  - "Production PyPI token still sitting in `~/.pypirc [pypi]` (one-time rescue path from 2026-05-20). Should be revoked on PyPI's web UI when convenient."
---

## Active feature

**bug-009 — ReAct + provider clients must round-trip `tool_calls`.**

Plan approved 2026-05-27. Targeting v0.2.4. Six implementation
chunks: (1) core `Message.tool_calls` field, (2) ReActLoop run +
stream populate, (3) `_message_to_<provider>` branches for bedrock /
openai / anthropic, (4) regression tests per layer, (5) docs +
release plumbing, (6) file bug-010 follow-up for the conformance-
harness gap.

Plan file: `/Users/khemchandjoshi/.claude/plans/cosmic-puzzling-shell.md`.
Branch: `fix/bug-009-react-loop-drops-tool-calls` (off main @ 97eb35a).

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
