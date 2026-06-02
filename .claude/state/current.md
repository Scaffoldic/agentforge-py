---
feature: bug-009 + bug-010 (tool_calls round-trip end-to-end)
state: pr-pending
branch: fix/bug-009-react-loop-drops-tool-calls
started_at: 2026-05-27
last_milestone_at: 2026-05-27
last_shipped: v0.2.3 — Upgrade-flow fix (bug-007) — PR #55 merged 2026-05-21; tag v0.2.3 pushed; GitHub Release published. 32 of 34 packages live on PyPI (presidio/nemo/llamaguard/evidently added 2026-05-27; phoenix + statsd remain).
blocker: null
flags_for_user:
  - "PR NOT OPENED YET. Branch fix/bug-009-react-loop-drops-tool-calls pushed with 6 green commits covering bug-009 + bug-010. URL: https://github.com/Scaffoldic/agentforge-py/pull/new/fix/bug-009-react-loop-drops-tool-calls. Suggested title: \"fix: round-trip tool_calls end-to-end (bug-009 + bug-010)\"."
  - "9 NEW untracked bug docs filed by user in parallel during this session: bug-012 through bug-020 in docs/bugs/. Not reviewed or committed yet — user WIP. (The earlier bug-011 collision was self-resolved: the runtime-doesnt-wire-mcp-bridge content is now at bug-020.)"
  - "32 of 34 packages live on PyPI at v0.2.3 (phoenix + statsd pending — final drip window 2026-05-28 ≈ 11:05 UTC)."
  - "bug-008 also queued for v0.2.4 (NOT IN THIS BRANCH): `version(\"agentforge\")` should be `version(\"agentforge-py\")` in cli/new_cmd.py and cli/_shared_scaffold.py. ~5 lines. Either fold into the v0.2.4 train (add a 7th commit) or ship as a separate small PR before tagging v0.2.4."
  - "v0.2.2 git tag is local-only (intentional — v0.2.3 supersedes). Pushing it burns a quota window without landing anything new."
  - "Production PyPI token still sitting in `~/.pypirc [pypi]` (one-time rescue path from 2026-05-20). Should be revoked on PyPI's web UI when convenient."
---

## Active feature

**bug-009 + bug-010 — tool_calls round-trip end-to-end.**

Both shipped together on a single branch because they're two
halves of the same problem: bug-009 round-trips `tool_calls`
in-flight (LLM history within one agent run), bug-010 round-trips
them across runs (chat history persisted to disk). External
downstream consumer surfaced both during a Generative-UI
integration design review on 2026-05-27.

**Branch:** `fix/bug-009-react-loop-drops-tool-calls` (off main @ `97eb35a`). Pushed.

**6 commits, all green through full pre-commit:**

| # | Commit | Bug | Scope |
|---|---|---|---|
| 1 | `294ab12` | 009 | core `Message.tool_calls` + ReActLoop populate + tests |
| 2 | `23be0e0` | 009 | bedrock/openai/anthropic `_message_to_<provider>` + tests |
| 3 | `638700a` | 009 | bug-009 status → fixed, new bug-011 (provider-conformance-harness) follow-up, CHANGELOG |
| 4 | `a53d68d` | 009 | workspace bump 0.2.3 → 0.2.4 (34 pyprojects + uv.lock + state/current.md) |
| 5 | `74e02eb` | 010 | `persist_steps` schema + helpers + StreamingEvent metadata enrichment + ChatResponse.tool_calls population |
| 6 | `f25b7f8` | 010 | 4 regression tests + bug-010 doc → fixed + CHANGELOG amend |

**Test count:** 1318 → 1332 (+14 regression tests across both bugs).

**Plan file:** `/Users/khemchandjoshi/.claude/plans/cosmic-puzzling-shell.md`.

## Pickup on resume (2026-05-28)

1. **Triage the 9 new bug docs (bug-012 … bug-020).** They appeared
   untracked during this session. Review each, decide which need
   fixes in v0.2.4 vs deferred, commit the doc files in a `docs:`
   chunk (likely a separate PR from the bug-009+010 branch). At
   minimum bug-020 (runtime-doesnt-wire-mcp-bridge) was previously
   colliding with the bug-011 slot and is now resolved.
2. **Decide bug-008 inclusion.** ~5-line fix
   (`version("agentforge")` → `version("agentforge-py")` in
   `cli/new_cmd.py` + `cli/_shared_scaffold.py`). Either fold into
   this branch as a 7th commit, or ship as a separate small PR before
   tagging v0.2.4.
3. **Open the PR.** `gh pr create` against main with the title above.
4. **Drip-publish phoenix + statsd at v0.2.3.** Final two packages.
   Window opens ≈ 2026-05-28 11:05 UTC. See `PYPI_PUBLISH_TRACKER.md`.
5. **After v0.2.3 drip completes AND bug-009+010 PR merges:** tag
   `v0.2.4`, push, run `release.yml`. 34 packages already version-
   bumped on this branch.

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
