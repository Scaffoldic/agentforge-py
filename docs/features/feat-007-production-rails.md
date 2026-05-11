# feat-007: Production rails

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-007 |
| **Title** | Production rails — cost budget, fallback chain, run_id propagation, idempotency |
| **Status** | proposed |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 |
| **Languages** | both |
| **Module package(s)** | `agentforge-core`, `agentforge` |
| **Depends on** | feat-001, feat-003 |
| **Blocks** | feat-002 (strategies must call BudgetPolicy), feat-009 (observability uses run_id) |

---

## 1. Why this feature

Most AI-agent frameworks treat production-readiness as someone else's problem.
You wire your own cost cap; you write your own retry/fallback logic; you bolt
correlation ids onto logs after your first incident. The result: every team
repeats the same work, often badly, and the first time their agent goes haywire
in production they discover the gaps the hard way.

Real failures we have seen:

- An LLM call loop with no budget cap costs $400 in 10 minutes before someone
  noticed.
- A provider rate-limit incident took down an agent for 6 hours because there
  was no cross-provider fallback.
- A bug report references "the agent did X yesterday" and is unfixable because
  no log line ties to a specific run.
- A retry on an idempotent-by-intention tool double-charged a customer because
  the retry didn't carry an idempotency key.

These are not exotic edge cases. Every production agent eventually hits all
four.

## 2. Why it must ship as framework

- **Cost cap is non-negotiable.** P3 (one LLM call costs USD; the framework
  knows it). The check has to run before every LLM call regardless of which
  strategy is in play. Only the framework can enforce this uniformly.
- **Fallback chain spans modules.** A fallback from Anthropic to Bedrock to
  OpenAI requires a single object that wraps three `LLMClient`s — that's a
  framework primitive, not an agent's responsibility.
- **`run_id` propagation through async code requires `ContextVar` /
  `AsyncLocalStorage` plumbing** that has to be set up by the agent runtime,
  not by each tool author.
- **Idempotency keys are protocol, not implementation.** Tools that mutate
  external state need a key; if every agent invents its own header, no shared
  proxy or dedupe layer can help.
- **Without framework ownership:** every team writes their own version of all
  four, often inconsistently, and the framework's "production-ready"
  promise dies.

## 3. How derived agents benefit

- **Day 0 — cost cap is on by default.** $1 per run. Nobody has to remember
  to add it. Override by `Agent(budget_usd=...)` or YAML.
- **Cross-provider fallback in three lines of YAML.** No code change.
- **Every log line, every metric, every claim record carries `run_id`
  automatically.** Cross-system correlation works.
- **Idempotency key auto-generated and propagated** through tool calls. Tools
  read it from `RunContext`; safe retries are free.
- **Standard incident-response runbook.** "Find the run_id in this log line;
  search elasticsearch with it; you have the full timeline." Works for every
  agent.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import Agent, FallbackChain, BudgetPolicy

agent = Agent(
    model=FallbackChain([
        "anthropic:claude-sonnet-4.7",
        "bedrock:anthropic.claude-sonnet-4.7",
        "openai:gpt-4o",
    ]),
    tools=[...],
    budget=BudgetPolicy(
        usd=5.00,
        max_tokens=200_000,
        max_iterations=50,
        error_streak_limit=3,
    ),
)

# Inside a tool — read the propagated run_id and idempotency key
from agentforge import current_run

async def charge_customer(amount_cents: int, customer_id: str) -> dict:
    ctx = current_run()
    return await stripe.charge(
        amount=amount_cents,
        customer=customer_id,
        idempotency_key=ctx.idempotency_key_for("charge_customer", customer_id),
    )
```

```python
# Logs auto-tagged
import logging
log = logging.getLogger(__name__)
log.info("Looking up user %s", uid)
# stdout: 2026-05-09 12:34:56 [run_id=01HX...ZYZ] INFO Looking up user U-42
```

### 4.2 Public API / contract

```python
# agentforge_core/production/budget.py — locked
class BudgetPolicy(BaseModel):
    usd: float = 1.0
    max_tokens: int = 200_000
    max_iterations: int = 25
    error_streak_limit: int = 3

    def check(self, state: AgentState) -> None:
        """Raises BudgetExceeded / GuardrailViolation if any limit breached."""

    def reserve(self, usd: float) -> None:
        """Pre-reserves budget for branching strategies (ToT, Multi-Agent)."""

    def commit(self, usd: float) -> None: ...
    def remaining_usd(self) -> float: ...

# agentforge_core/production/fallback.py
class FallbackChain:
    def __init__(self, providers: list[str | LLMClient], *,
                 retry_on: tuple[type[Exception], ...] = (RateLimitError, ProviderError),
                 attempts_per_provider: int = 1) -> None: ...
    async def call(self, *args, **kwargs) -> LLMResponse: ...

# agentforge_core/production/run_id.py
def current_run() -> RunContext:
    """Returns the live RunContext from the ContextVar / AsyncLocalStorage."""

class RunContext(BaseModel):
    run_id: str
    started_at: datetime
    parent_run_id: str | None
    idempotency_seed: str

    def idempotency_key_for(self, *parts: Any) -> str:
        """Stable key derived from (run_id, parts) — safe to retry within a run."""

# agentforge_core/production/logging.py
class RunIdFilter(logging.Filter):
    """Attaches `run_id` to every LogRecord. Auto-installed on root logger
    by Agent.__init__."""
```

### 4.3 Internal mechanics

```
Agent.run(task)
   │
   ├── RunContext(run_id=ULID(), idempotency_seed=hash(task)) → bound to ContextVar
   │
   ├── RunIdFilter attached to root logger (idempotent install)
   │
   ├── BudgetPolicy.start(usd=1.00, ...)
   │
   ├── strategy.run(state):
   │     ┌ before each LLM call:
   │     │   BudgetPolicy.check(state)        ← raises if breached
   │     ├ branching strategies pre-call:
   │     │   BudgetPolicy.reserve(estimated_per_branch × n_branches)
   │     ├ on each tool call:
   │     │   tool runs in a subtask that inherits ContextVar
   │     ├ on LLM error:
   │     │   FallbackChain.call(...) tries next provider
   │     └ on tool error:
   │         error_streak += 1; trips guardrail at limit
   │
   ├── BudgetPolicy.commit_actual_cost()
   │
   └── return RunResult (with run_id, cost_usd, retry_provider_used)
```

`FallbackChain` is itself an `LLMClient` — it implements the same ABC, so any
strategy that takes an `LLMClient` accepts a chain transparently.

### 4.4 Module packaging

All in `agentforge-core` and `agentforge`. No opt-in module needed; production
rails are always on.

### 4.5 Configuration

```yaml
agent:
  budget:
    usd: 5.0
    max_tokens: 200000
    max_iterations: 50
    error_streak_limit: 3

  fallback:
    providers:
      - "anthropic:claude-sonnet-4.7"
      - "bedrock:anthropic.claude-sonnet-4.7"
    retry_on: ["RateLimitError", "ProviderError"]
    attempts_per_provider: 1

logging:
  run_id_filter: true       # default true
  level: "INFO"
```

## 5. Plug-and-play & upgrade story

Always installed. Adding fallback later: edit YAML, no code change. Tightening
budget: edit YAML, no code change. New guardrail in a future framework version
(e.g. `total_run_seconds`): adds with safe default; opt-in to lower limits.

## 6. Cross-language parity

`run_id` via `ContextVar` (Python) and `AsyncLocalStorage` (TS — Node 16+).
`RunIdFilter` (Py logging filter) ↔ pino/winston transformer (TS). `BudgetPolicy`
and `FallbackChain` shape identical.

## 7. Test strategy

- **Budget breach tests:** every budget kind triggers the right exception at
  the right point.
- **Pre-reservation correctness:** ToT with 4 branches × $0.20 reserves $0.80
  upfront and never exceeds.
- **Fallback chain:** mock first provider to error; second succeeds; verify
  `RunResult.provider == second`.
- **`run_id` propagation:** spawn 5 nested async tasks; every one sees the same
  `run_id`.
- **Idempotency key stability:** same `(run_id, parts)` always yields same key;
  different parts yield different keys.
- **Log filter:** every `log.info(...)` line in tests has `run_id=...` attached.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| `BudgetPolicy` overhead on every iteration | Negligible — it's a few comparisons; benchmarked in conformance suite |
| Fallback masks provider bugs (silent retry) | `RunResult.fallback_history` records every attempt; not silent |
| `RunIdFilter` collides with user's existing log filters | Idempotent install; documented; opt-out via `logging.run_id_filter: false` |
| Idempotency seed predictability | Seeded from `hash(task + run_id)`; sufficiently unpredictable; don't use for security tokens |
| Cross-thread propagation in Python | Python `ContextVar` works across `await` but not raw threads; doc the pattern; provide `bind_run(fn)` helper for thread targets |

## 9. Out of scope

- Distributed tracing (OTel spans). Handled in feat-009 as a hook on top of
  `run_id`; this feature provides the correlation primitive.
- Per-tool budgets. The single run-level budget covers it; per-tool quotas
  belong in a tool-rate-limiter wrapper, not in core.
- Automatic retry of agent runs (re-running the whole agent on failure).
  Out of scope; orchestration layer above the agent owns this.

## 10. References

- [`architecture.md`](../design/architecture.md) §7
- [`design-principles.md`](../design/design-principles.md) — P3, P4
- feat-001 (Agent wires this), feat-002 (strategies call BudgetPolicy.check),
  feat-003 (FallbackChain wraps LLMClient), feat-009 (observability sits on run_id)
- Archived: `docs/archive/cr/CR-008-cross-provider-fallback.md`,
  `CR-010-run-id-context-propagation.md`, `CR-013-idempotency-keys.md`,
  `docs/archive/subsystem-production-rails.md`

---

## Implementation status

**Status: shipped (Python). TypeScript port pending.**

feat-007's surface largely shipped under feat-001:

| Piece | Status |
|---|---|
| `BudgetPolicy` (USD / token / iteration / error-streak caps) | shipped feat-001 |
| `RunContext` + `current_run()` (ContextVar-bound run state) | shipped feat-001 |
| `RunContext.idempotency_key_for(*parts)` | shipped feat-001 |
| `RunIdFilter` (auto-tags log records with run_id) | shipped feat-001 |
| `BudgetPolicy.reserve` / `commit` / `record_error` / `record_success` | shipped feat-001; consumed feat-002 |
| **`FallbackChain`** | **shipped this PR** |

`FallbackChain` landed via PR #11 on `feat/007-production-rails`
across three chunks:

| Chunk | Commit | Scope |
|---|---|---|
| 1 | `6bdd066` | `FallbackChain` class (`agentforge_core/production/fallback.py`); 23 unit tests |
| 2 | `2e7d2d3` | Top-level re-export (`from agentforge import FallbackChain`); 4 Agent-integration tests |
| 3 | (this) | CHANGELOG, Implementation status, Runbook section, PR |

### Public surface delivered

```python
from agentforge import Agent, FallbackChain

chain = FallbackChain(
    [
        "anthropic:claude-sonnet-4.7",
        "bedrock:anthropic.claude-sonnet-4.7",
        "openai:gpt-4o",
    ],
    retry_on=(RateLimitError, ProviderError),  # default
    attempts_per_provider=1,                   # default
)
agent = Agent(model=chain, tools=[...])
```

### Deviations from this spec

- **`FallbackChain` is NOT re-exported from
  `agentforge_core.production`.** The natural location creates a
  circular import (`production/__init__.py` → `fallback` →
  `contracts.llm` → `production.exceptions.CapabilityNotSupported`
  → back into `production/__init__.py` while still loading). The
  workaround documented inline in `production/__init__.py`:
  `FallbackChain` is imported from the submodule directly inside
  `agentforge_core/__init__.py`, which runs *after* `production`
  finishes. Users reach it via
  `from agentforge_core import FallbackChain` or
  `from agentforge import FallbackChain`.
- **`stream` is not supported** in v0.1. Streaming with
  cross-provider fallback semantics is harder than the unary call
  (events from provider N might partially arrive before fallback
  N+1 kicks in). `chain.stream(...)` raises
  `CapabilityNotSupported` unconditionally. Callers needing
  streaming pick a single provider.
- **Capability-intersection rule** for optional methods
  (`call_with_cache`, `call_with_thinking`) — locked in by user
  decision before chunk 1. The chain's `capabilities()` returns
  the intersection of every wrapped provider's capabilities, and
  optional methods raise `CapabilityNotSupported` unless every
  wrapped provider declares the capability.
- **Default `retry_on` includes `AuthenticationError`** via
  inheritance (`AuthenticationError` extends `ProviderError`).
  Intentional: one provider's auth being misconfigured is a
  legitimate reason to try the next provider with its own auth.
  Callers wanting tighter behaviour pass
  `retry_on=(RateLimitError,)`.

### What's *not* yet implemented

- **`RunResult.retry_provider_used`**: spec mentions tracking
  which provider answered. `FallbackChain.last_used_provider`
  exposes the index for diagnostics, but `RunResult` does not yet
  carry the field. Adding it is a minor bump on the locked
  `RunResult` shape; lands in a follow-up or alongside feat-009
  (Observability) where the field becomes most useful.
- **Provider-level retry backoff** at the chain level. Today the
  chain just retries `attempts_per_provider` times in immediate
  succession. Backoff sits per-provider (the bedrock driver
  already implements bounded exponential backoff with jitter
  internally).
- **TypeScript port** of the entire feat-007 surface.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented. When feat-011 (Copier scaffolding) and
feat-019 (runbook system) ship, this section is consumed by the
templating engine and rendered into scaffolded agent projects.

### How do I configure cross-provider fallback?

Wrap your providers in `FallbackChain` and pass it as `model`:

```python
from agentforge import Agent, FallbackChain

chain = FallbackChain([
    "anthropic:claude-sonnet-4.7",          # primary
    "bedrock:anthropic.claude-sonnet-4.7",  # fallback 1
    "openai:gpt-4o",                        # fallback 2
])
agent = Agent(model=chain, tools=[...])
```

Order matters — the chain tries the **first** provider first and
only falls back on a `retry_on` exception. Put the cheapest /
fastest / most-trusted provider first.

### How do I tune retries?

Two levers:

```python
chain = FallbackChain(
    providers=["anthropic:claude-sonnet-4.7", "bedrock:..."],
    retry_on=(RateLimitError, ServiceError),  # narrow the set
    attempts_per_provider=3,                  # try each provider 3x
)
```

- `retry_on` is the **set of exception types** that trigger
  fallback. Default `(RateLimitError, ProviderError)` covers
  every transient provider error, including auth/model-not-found
  (since they're `ProviderError` subclasses). Pass a narrower
  tuple to keep falling back only on rate limits or service
  errors.
- `attempts_per_provider` is how many times each provider is
  retried **before** moving to the next one. Default 1 (no
  retry; first failure → next provider).

### How do I set a budget cap on top of fallback?

`BudgetPolicy` and `FallbackChain` are independent. Combine:

```python
from agentforge import Agent, BudgetPolicy, FallbackChain

agent = Agent(
    model=FallbackChain([...]),
    budget=BudgetPolicy(usd=5.0, max_tokens=200_000, max_iterations=50),
)
```

Failover cost counts against the same budget — falling over to a
more expensive provider exhausts the budget sooner, tripping
`BudgetExceeded` per the existing semantics.

### How do I read the run_id from inside a tool?

```python
from agentforge import current_run

@tool
def charge_customer(amount_cents: int, customer_id: str) -> dict:
    """Charge a customer (uses the run's idempotency key)."""
    ctx = current_run()
    return stripe.charge(
        amount=amount_cents,
        customer=customer_id,
        idempotency_key=ctx.idempotency_key_for("charge", customer_id),
    )
```

`current_run()` reads the per-run `RunContext` from the ContextVar
`Agent.run()` binds. Safe to call from any tool body or any code
running inside `Agent.run()`'s scope.

`ctx.idempotency_key_for(*parts)` is **stable for the lifetime of
one run** — retries within the run reuse the same key, so
external services (Stripe, SQS, etc.) dedupe them. Different runs
get different keys.

### How do I tag my logs with run_id automatically?

Already on by default:

```python
import logging
log = logging.getLogger(__name__)
log.info("Looking up user %s", user_id)
# stdout: 2026-05-10 14:23:01 [run_id=01HX...ZYZ] INFO Looking up user U-42
```

`Agent.__init__` installs `RunIdFilter` on the root logger
(idempotent — installing again is a no-op). To opt out:
`Agent(install_log_filter=False)`.

### How do I debug "which provider answered my call"?

Read `chain.last_used_provider` after a call:

```python
chain = FallbackChain(["anthropic:...", "bedrock:..."])
agent = Agent(model=chain)
result = await agent.run("hello")
print(f"answered by provider index {chain.last_used_provider}")
# 0 = anthropic, 1 = bedrock
```

`None` until the first successful call; the index is 0-based and
reflects the chain's construction order.

### How do I debug "every provider failed"?

The **last** provider's exception bubbles up. The chain logs a
WARNING for each fallback transition:

```
WARNING agentforge_core.production.fallback: provider 1/3 (BedrockClient)
        raised RateLimitError (attempt 1/1); trying next provider
WARNING agentforge_core.production.fallback: provider 2/3 (BedrockClient)
        raised RateLimitError (attempt 1/1); trying next provider
```

Set `agentforge_core.production.fallback` to DEBUG or INFO during
development to see the full transition log. WARNINGS are usually
sufficient in production.

### When should I NOT use FallbackChain?

- **Streaming**: `FallbackChain.stream` raises
  `CapabilityNotSupported`. Pick a single provider for streaming.
- **Providers with very different capabilities**: the chain's
  `capabilities()` is the intersection. Wrapping a
  caching-supporting Anthropic with a non-caching OpenAI means
  `chain.supports("caching")` is `False`. Either use
  `FallbackChain` only over capability-equivalent providers, or
  avoid declaring the capability.
- **When `AuthenticationError` is config drift, not transient**:
  the default `retry_on` falls back on auth errors too. If your
  auth-error means "credentials rotated and need updating",
  failing over hides that signal. Pass
  `retry_on=(RateLimitError, ServiceError, TimeoutError)` for
  stricter behaviour.
