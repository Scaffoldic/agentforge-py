---
feature: v0.2.4 MCP/chat/config cluster — bug-020 + bug-014 (MCP runtime wiring)
state: pr-pending
branch: fix/bug-020-mcp-runtime-wiring
started_at: 2026-06-02
last_milestone_at: 2026-06-02
last_shipped: v0.2.3 — Upgrade-flow fix (bug-007), PR #55 merged 2026-05-21; tag + GitHub Release published. ALL 34 packages now live on PyPI at v0.2.3 (drip completed 2026-05-28). v0.2.4 in progress on main (0.2.4 version bump merged via #58) but NOT yet tagged/released.
blocker: null
resume: evening IST 2026-06-02
flags_for_user:
  - "PR #59 OPEN (fix/bug-020-mcp-runtime-wiring): bug-020 P0 + bug-014 P1. 2 commits (9282000, 25a43bb), full gate green, pushed. https://github.com/Scaffoldic/agentforge-py/pull/59 — awaiting merge."
  - "PRs #57 (docs triage) + #58 (bug-009/010 fix) MERGED to main. main at version 0.2.4."
  - "REMAINING v0.2.4 cluster (not started), suggested order: bug-012 (adapter .→_ separator) → bug-017 (Bedrock tool-name validator + docs) → bug-015 (meta extra chain agentforge-py[mcp]→agentforge-mcp[mcp] + audit other vendor modules) → bug-019 (config string→{name} normaliser: evaluators + guardrail input/output/tool_gates) → bug-018 (SqliteChatHistory upsert + ChatHistoryStore.create_session ABC) → bug-013 (from_stdio/from_http auto register_tools) → enh-001 (HTTP server transport)."
  - "bug-008 still queued for v0.2.4 (NOT done): version(\"agentforge\")→version(\"agentforge-py\") in cli/new_cmd.py + cli/_shared_scaffold.py. ~5 lines."
  - "v0.2.4 CHANGELOG header is `## [0.2.4] — unreleased`; set the date + tag only after the whole cluster lands."
  - "PyPI v0.2.3 drip COMPLETE (34/34). Post-completion chores: revoke ~/.pypirc [pypi] token; convert projects to Trusted Publishing; delete PYPI_PUBLISH_TRACKER.md (see that file + memory)."
---

## Active feature

**v0.2.4 MCP/chat/config cluster.** Eight framework defects + one
enhancement filed against v0.2.3 from the first live Bedrock-backed
MCP integration. Triaged, verified against source, and tracked in
`docs/bugs/bug-012…020` + `docs/enhancements/enh-001` (PR #57, merged).
Each bug doc carries a "Framework-level vs derived-agent-level"
section; all eight are framework-level. The whole cluster folds into
**v0.2.4** (no release until it all lands).

**In flight — PR #59** (`fix/bug-020-mcp-runtime-wiring`, off main):

| # | Commit | Bug | Scope |
|---|---|---|---|
| 1 | `9282000` | 014 | `MCPBridge.from_config` pure-data; async `start()` materialises deferred client specs; `_await_sync` deleted; `attach_local_tools` + `MCPServer.set_tools`; list-form `command:`. Tests. |
| 2 | `25a43bb` | 020 | `agentforge_core.contracts.protocol_bridge.ProtocolBridge` (runtime_checkable); `Agent(protocol_bridges=)` + close on exit; `build_protocols_from_config` wired into `build_agent_from_config` (also wires native `agent.tools` — previously zero-caller gap); expose rejected (stdio-hijack guard). Tests. feat-013 §10 + CHANGELOG. |

Full pre-commit gate green on both commits. Scope: **consume path
only**; server-side `expose` runtime-wiring deferred (with enh-001).

## Pickup on resume (evening IST 2026-06-02)

1. **Merge PR #59** (bug-020 + bug-014) once reviewed/CI-green.
2. **Work the rest of the cluster** (each its own `fix/bug-NNN-*`
   branch off main, folding into v0.2.4), suggested order:
   - **bug-012** — adapter `.`→`_` separator (`adapter.py:34`).
   - **bug-017** — defensive Bedrock tool-name validator
     (`[a-zA-Z0-9_-]+`) + document the constraint (feat-004/003/013
     specs + `@tool` docstring + templates). Backs up bug-012.
   - **bug-015** — meta extra chain: `agentforge/pyproject.toml:105`
     `mcp = ["agentforge-mcp ~= 0.2.4"]` → `["agentforge-mcp[mcp] ~= 0.2.4"]`;
     fix the `ModuleError` text; audit other vendor modules for the
     same broken chain.
   - **bug-019** — `mode="before"` string→{name} normaliser for
     `modules.evaluators` + guardrail `input`/`output`/`tool_gates`
     (both EvaluatorEntry AND GuardrailEntry are broken).
   - **bug-018** — `SqliteChatHistory.update_session_metadata` upsert
     (option 1, minimal) + `ChatHistoryStore.create_session()` ABC
     (option 2, contract fix) — both in one PR.
   - **bug-013** — `from_stdio`/`from_http` auto-call `register_tools()`.
   - **enh-001** — HTTP MCP server transport (may slip to 0.2.5).
3. **bug-008** (~5 lines) — fold in somewhere before tagging.
4. **Tag v0.2.4** only after the cluster lands: set CHANGELOG date,
   push tag, run `release.yml` (34 packages already at 0.2.4 on main).
5. **PyPI post-drip chores** (drip is 34/34 done): revoke `~/.pypirc`
   token, Trusted Publishing conversion, delete `PYPI_PUBLISH_TRACKER.md`.

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
