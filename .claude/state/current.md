---
feature: none
state: idle
branch: main
started_at: null
last_milestone_at: 2026-05-12T00:30
last_shipped: feat-017 shipped via PR #20 (awaiting merge)
blocker: null
flags_for_user: []
---

## Active feature

*None — awaiting next pick.*

## Last shipped

[`feat-017 — CLI runtime`](../../docs/features/feat-017-cli-runtime.md)
shipped in PR #20 with full Python scope:

- CLI: `agentforge run` (+ `--replay`/`--record`),
  `agentforge eval`, `agentforge debug`, `agentforge db
  {migrate,backup,restore,purge,query}`, `agentforge health`.
- Foundations: `MemoryStore.delete()` on the ABC + every driver,
  run-recording protocol (`__step`/`__eval`/`__run` categories),
  `ReplayLLMClient` + `replay_tools`, `build_agent_from_config`.
- Exit codes locked at 0/1/2/3/4/5.

Deviations recorded in the spec §10:

- `agentforge status` (spec) → `agentforge health` (to avoid
  collision with feat-011's scaffolding `status`).
- argparse instead of Typer.
- Templates ship in-wheel (inherited from feat-011).
- `db migrate` is a no-op for `InMemoryStore` / `SqliteMemoryStore`.
- TS engine and CI upgrade matrix deferred.

## Next pick candidates (canonical numbering)

- **feat-016** — Testing framework (MockLLMClient + fake tools +
  pytest/vitest helpers in `agentforge-testing`).
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
