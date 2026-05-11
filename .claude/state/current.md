---
feature: none
state: idle
branch: main
started_at: null
last_milestone_at: 2026-05-12T01:30
last_shipped: feat-016 shipped via PR #21 (awaiting merge)
blocker: null
flags_for_user: []
---

## Active feature

*None — awaiting next pick.*

## Last shipped

[`feat-016 — Testing framework`](../../docs/features/feat-016-testing-framework.md)
shipped in PR #21 with full Python scope:

- `agentforge.testing` namespace inside the runtime package:
  `MockLLMClient` (from_script / deterministic / from_recording),
  `FakeTool`, `FakeLLMClient`, `agent_factory`, pytest fixtures
  (`mock_llm`, `temp_memory_store`), conformance re-exports
  (`run_memory_conformance`, `run_strategy_conformance`,
  `run_vector_conformance`), `record_llm` + `load_recording`.
- `agentforge-testing` sister package (new workspace member):
  `GoldenSetRunner` (exact / contains / regex / any_of),
  `assert_snapshot` (UPDATE_SNAPSHOTS env), `analyze_recording`
  → `RecordingStats`.
- 22 unit tests across both packages.

Deviations recorded in spec §10:

- `_testing` private namespace retained as a compat shim.
- `MockLLMClient` doesn't yet satisfy a `run_llm_conformance`
  harness (none exists in core yet).
- Replay matches by sequence today; request_hash persisted for
  future hash-keyed replay.
- VCR-style full redaction pipeline deferred; basic redaction
  (api_key / authorization / bearer) ships.
- TypeScript port deferred.

## Next pick candidates (canonical numbering)

- **feat-018** — Safety guardrails (InputValidator /
  OutputValidator / ToolCallGate + prompt-injection + PII +
  capability gates).
- **feat-013** — MCP integration (consume MCP tool servers +
  expose agent tools as MCP).
- **feat-019** — Developer experience (16 runbooks + AGENTS.md /
  CLAUDE.md / .cursorrules shipped with every scaffold).
- **feat-014** / **feat-015** / **feat-020** — see specs.
- Vendor observability sub-feats (langfuse/phoenix/evidently/statsd).

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
