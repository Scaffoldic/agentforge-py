---
feature: v0.2.4 MCP/chat/config cluster — bug-015 (meta extra-chain packaging)
state: pr-raised
branch: fix/bug-015-meta-extra-chain
started_at: 2026-06-02
last_milestone_at: 2026-06-03
last_shipped: v0.2.3 — Upgrade-flow fix (bug-007), PR #55 merged 2026-05-21; tag + GitHub Release published. ALL 34 packages now live on PyPI at v0.2.3 (drip completed 2026-05-28). v0.2.4 in progress on main (0.2.4 version bump merged via #58) but NOT yet tagged/released.
blocker: null
resume: null
flags_for_user:
  - "PR #62 OPEN (fix/bug-015-meta-extra-chain): bug-015 P2 — meta-package extras didn't chain sister vendor-SDK extras. Audited all 34 pkgs; fixed 12 missing chains + `[all]`, 1 phantom extra (bedrock), 1 eager-import-as-optional (agentforge-chat aiosqlite → hard dep). mcp ModuleError text updated. New generic test_extras_chain.py locks the invariant. 1 commit (9622d7e), full gate + Live CI green. https://github.com/Scaffoldic/agentforge-py/pull/62 — awaiting merge."
  - "MERGED to main: #57 (docs triage), #58 (bug-009/010), #59 (bug-020+bug-014 MCP runtime wiring), #60 (bug-012 MCP `.`→`__`), #61 (bug-017 tool-name charset validator, 077795a). main at version 0.2.4."
  - "REMAINING v0.2.4 cluster (after #62), suggested order: bug-019 (config string→{name} normaliser: evaluators + guardrail input/output/tool_gates — both EvaluatorEntry AND GuardrailEntry broken) → bug-018 (SqliteChatHistory upsert + ChatHistoryStore.create_session ABC) → bug-013 (from_stdio/from_http auto register_tools) → enh-001 (HTTP server transport)."
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

**Landed — PR #59 MERGED** (`fix/bug-020-mcp-runtime-wiring`, merge
commit `c2f1132`): bug-014 (`MCPBridge.from_config` pure-data + async
`start()` materialises clients; `attach_local_tools` + `set_tools`;
list-form `command:`) and bug-020 (`ProtocolBridge` runtime_checkable
contract; `Agent(protocol_bridges=)` + close on exit;
`build_protocols_from_config` wired into `build_agent_from_config`,
which also fixed the zero-caller native-`agent.tools` gap; `expose`
rejected as stdio-hijack guard). The cluster unblocker is in main.

**Merged — PR #60** (`fix/bug-012-mcp-adapter-separator`, merge commit
`3cf2bdc`): MCP tool-name separator `.`→`__`. CI Live job initially
failed (env-gated `test_mcp_live.py` asserted the old `echo.echo`;
local pre-commit doesn't run live tests) — fixed in commit `0bc8386`.

**Merged — PR #61** (`fix/bug-017-tool-name-validator`, 077795a):
tool-name charset validator at all 3 provider boundaries.

**In flight — PR #62** (`fix/bug-015-meta-extra-chain`, off main):
bug-015 P2 — meta-package extras didn't chain sister vendor-SDK extras
(`pip install agentforge-py[mcp]` installed the wrapper but not the SDK).
Audited all 34 pkgs: fixed 12 missing chains + `[all]`, 1 phantom extra
(`bedrock` → bare), 1 eager-import-as-optional (`agentforge-chat`
aiosqlite → hard dep, matching memory-sqlite). mcp `ModuleError` text →
`agentforge-mcp[mcp]`. New `test_extras_chain.py` locks the invariant
generically. 1 commit (`9622d7e`), full gate + Live CI green. Awaiting
merge.

## Pickup on resume

1. **Merge PR #62** (bug-015) once reviewed/CI-green.
2. **Work the rest of the cluster** (each its own `fix/bug-NNN-*`
   branch off main, folding into v0.2.4), suggested order:
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
