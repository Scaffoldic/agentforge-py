---
feature: feat-007-production-rails
state: analysing
branch: feat/007-production-rails
started_at: 2026-05-10T17:30
last_milestone_at: 2026-05-10T17:30
last_shipped: feat-004 (Tools system) shipped via PR #10 @ 2b1a37c
blocker: null
flags_for_user: ["design-awaiting-approval"]
---

## Active feature

[`feat-007 — Production rails`](../../docs/features/feat-007-production-rails.md)

Per pipeline §1: lowest-numbered proposed feature with deps shipped.
feat-007 deps: feat-001 ✓, feat-003 ✓.

## Scope (from canonical spec §4)

Most of feat-007's surface **already shipped under feat-001**. The
only remaining piece is `FallbackChain`. The user clarified they
saw "production rails" as covering all modern guardrails — that's
feat-018 (Safety), separate. feat-007 is narrower:

| Piece | Status |
|---|---|
| `BudgetPolicy` (cost / token / iteration / error-streak caps) | ✓ shipped feat-001 |
| `RunContext` + `current_run()` (ContextVar-bound run state) | ✓ shipped feat-001 |
| `RunContext.idempotency_key_for(*parts)` | ✓ shipped feat-001 |
| `RunIdFilter` (auto-tags log records with run_id) | ✓ shipped feat-001 |
| `BudgetPolicy.reserve` / `commit` / `record_error` / `record_success` | ✓ shipped feat-001 / consumed feat-002 |
| **`FallbackChain`** — cross-provider failover wrapping multiple `LLMClient`s | ❌ **this PR** |

## FallbackChain design

Per spec §4.2:

```python
class FallbackChain(LLMClient):
    def __init__(
        self,
        providers: list[str | LLMClient],
        *,
        retry_on: tuple[type[Exception], ...] = (RateLimitError, ProviderError),
        attempts_per_provider: int = 1,
    ) -> None: ...
```

Key invariants:

1. **Implements `LLMClient` ABC** — strategies that accept any
   `LLMClient` accept a chain transparently.
2. **String providers resolve via the resolver**, same path
   `Agent(model="bedrock:...")` uses today.
3. On `retry_on` exception → try next provider (after retries on
   the current one if `attempts_per_provider > 1`).
4. **Last provider's exception bubbles up** if every provider
   exhausts retries.
5. **Tracks which provider answered** so `RunResult` can include
   `retry_provider_used` (post-merge follow-up may add the field
   to `RunResult` — out of scope for this PR; chain just records).
6. `capabilities()` returns the **intersection** of every wrapped
   provider's capabilities — a chain can only honestly claim a
   capability every fallback supports. Conservative.
7. `close()` calls `close()` on every wrapped provider (in
   reverse-construction order so partial failures don't leak).

## Open design questions

- **Where does `FallbackChain` live?** Spec §4.2 puts it at
  `agentforge_core/production/fallback.py`. That keeps it in the
  contract layer alongside `BudgetPolicy` and `RunContext`. ✓
  agreed.
- **Should it accept arbitrary callables (`call_with_cache`,
  `call_with_thinking`, `stream`)?** Spec only mentions `call`.
  Plan: forward `call` as the canonical path; `call_with_cache`
  and `call_with_thinking` raise `CapabilityNotSupported` from
  the chain unless every wrapped provider supports them
  (capability-intersection rule). `stream` is harder — defer to
  a follow-up if needed.
- **How are exceptions retried within a single provider?** Spec
  says `attempts_per_provider`. Each attempt is a separate `await
  provider.call(...)` call; no exponential backoff at the chain
  level (providers can do their own).

## Proposed chunks (3 total — small feature)

1. **`FallbackChain` class** in
   `agentforge_core/production/fallback.py`. Implements `LLMClient`
   surface (`call`, `close`, `capabilities`, `supports`). Resolves
   string providers via the resolver. Tracks `last_used_provider`
   for diagnostic purposes. Unit tests cover: success on first
   provider, retry-on-RateLimitError → second provider succeeds,
   all providers fail → last exception bubbles, capabilities
   intersection, attempts_per_provider, close() cascades, raises
   CapabilityNotSupported for `call_with_cache` /
   `call_with_thinking` unless every provider supports them.

2. **Re-export from `agentforge` top-level** so
   `from agentforge import FallbackChain` works. Update
   `Agent.__init__` to accept `model=FallbackChain([...])` (it
   already accepts `LLMClient`; verify the path).

3. **CHANGELOG + Implementation status + Runbook section + PR.**
   Update `docs/features/feat-007-production-rails.md` with:
   - **Implementation status** section with chunk-by-chunk mapping.
   - **`## Runbook` section** (new policy locked in 2026-05-10):
     task-oriented "how do I…" content for agent developers using
     `FallbackChain` — config example, picking providers, retry
     tuning, debugging which provider answered. Future feat-011 +
     feat-019 will consume this section into scaffolded agent
     projects.
   - CHANGELOG entry under [Unreleased]/Added.
   - Mark feat-007 shipped; raise PR.

## TODO before next milestone

- [ ] User approves this analysis + chunk plan.
- [ ] On approval: state → `designing` → `implementing`; begin
      chunk 1.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/features/feat-007-production-rails.md`
5. `docs/roadmap.md`
