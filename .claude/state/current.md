---
feature: none
state: idle
branch: main
started_at: null
last_milestone_at: 2026-05-12
last_shipped: feat-014 v0.2 production A2A runner + discovery + streaming shipped via PR #33 (merged 2026-05-12)
blocker: null
flags_for_user: []
---

## Active feature

*None — awaiting next pick.*

## Last shipped

[`feat-014 v0.2 follow-up`](../../docs/features/feat-014-a2a-protocol.md)
shipped via PR #33 (merged 2026-05-12). Closes the three
items v0.1 deferred in one bundle:

- **Production HTTP runner**: `_HTTPXClientRunner` +
  `_UvicornServerRunner` wrap `httpx.AsyncClient` /
  `uvicorn.Server`; v0.1's `NotImplementedError` stubs gone.
  Bodies remain `# pragma: no cover`; coverage proven by the
  new `@pytest.mark.live` suite.
- **A2A discovery**: `GET /a2a/v1/info` returns the full
  `A2APeerInfo` shape (description + JSON-Schema input
  shapes per endpoint). `discover_peer(peer)` +
  `A2ABridge.discover_all()` + `bridge.peer_info` cache.
  Client-side only — no central registry.
- **Bi-directional streaming**: `POST /a2a/v1/calls/stream`
  returns SSE `A2AChunk` frames; `agent_call_stream(...)`
  yields them. Step-level granularity for v0.2 (one chunk per
  agent `Step` plus terminal `done` / `error`).
- **Non-gating `live` CI job** running `pytest -m live`
  across packages with `tests/integration/test_*_live.py`
  (mcp + a2a; threshold was ≥ 2).

Deferred to v0.3 (recorded in spec §10):

- Real per-token LLM streaming via `ReasoningStrategy.stream()`
  (lands with feat-020's strategy-level streaming follow-up).
- Per-run hook kwarg on `Agent.run` (cleanup of the
  streaming server's transient `agent._on_step.append(...)`).
- Unifying `A2AChunkKind` with `ChatChunkKind` under a
  framework-wide `StreamingChunk`.
- Hardening the `live` CI job to gate merge.

### Previously

[`feat-020 — Chat agents (v0.2 scope)`](../../docs/features/feat-020-chat-agents.md)
shipped in PR #26 (merged 2026-05-12).

## Next pick candidates

v0.1.0 is tagged + published. We're now mid-v0.2.0 cycle.
Sequence continues v0.3 → v0.4 → 1.0 per
[ADR-0015](../../docs/adr/0015-coordinated-release-train.md).

**v0.2.0 remaining backlog:**

- **feat-020 follow-ups** —
  `agentforge-chat-history-postgres`,
  `agentforge-chat-history-redis`, `agentforge-chat-slack`
  adapter, real per-token streaming through the strategy
  loop (also unblocks A2A per-token streaming), cross-process
  locking, provider-aware tokeniser.
- **feat-009 vendor backends** — `agentforge-langfuse`,
  `-phoenix`, `-evidently`, `-statsd`.
- **Sub-feat backlog** (no canonical numbers yet) — GraphRAG
  hybrid retrieval, BM25 + vector hybrid search, `Reranker`
  ABC, schema migrations.

**Already shipped on the v0.1 → v0.2 line:**

- feat-013 v0.2 — production MCP runner (PR #32).
- feat-014 v0.2 — production A2A runner + discovery +
  streaming (PR #33).

After v0.2.0 lands, v0.3.0 is reserved for the next round of
community / ecosystem feedback (intentionally empty at v0.1.0
cut). v0.4.0 brings TypeScript to parity with the Python
v0.2 surface per
[ADR-0002](../../docs/adr/0002-multi-language-python-typescript.md).

Spec `Target version` metadata is aspirational and predates
any release. When a feature lands earlier or later than its
declared target, the tag wins.

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
