# ADR-0010: Production rails (cost, run_id, fallback, idempotency) framework-owned

## Metadata

| Field | Value |
|---|---|
| **Number** | 0010 |
| **Title** | Production rails framework-owned |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, production |

---

## 1. Context and problem statement

Production-readiness — cost cap, correlation id, retry/fallback,
idempotency — is the part of agent-building that almost every team
re-implements at slightly different fidelity, usually after their first
incident. Most frameworks treat these as the developer's concern.

How do we deliver these as defaults so a fresh agent has them on day 1
without ceremony, while still allowing agents to tune or extend them?

## 2. Decision drivers

- Cost incidents are unrecoverable user-trust events
- Cross-system correlation requires consistency
- Fallback chain across providers is multi-module; ownership must be
  central
- Idempotency keys are protocol, not implementation
- Production rails must be loud defaults (P6), not opt-ins

## 3. Considered options

1. **Per-agent implementation** — every team writes their own
2. **Optional middleware module** — opt-in stack of production
   guardrails
3. **Framework-owned, on-by-default** — `BudgetPolicy`, `RunContext`,
   `FallbackChain`, idempotency-key derivation in `agentforge-core` /
   `agentforge`; always wired by `Agent`
4. **External service** — production rails live outside the agent
   process (proxy, sidecar)

## 4. Decision outcome

**Chosen: Option 3 — Framework-owned, on-by-default.**

`BudgetPolicy(usd=1.0)` is the default; checked before every LLM call,
across every reasoning strategy (enforced by conformance test).
`run_id` is generated on `Agent.run()`, propagated via `ContextVar`
(Python) / `AsyncLocalStorage` (TS). `FallbackChain` is itself an
`LLMClient` so it composes with strategies transparently.
`current_run().idempotency_key_for(*parts)` produces stable keys for
tools that need them. All four primitives are framework-level so no
team can accidentally bypass them.

### Positive consequences

- Day-0 agents have production rails wired
- Rules are uniform across every agent in an organisation
- Cross-system runbooks ("search by run_id") work everywhere
- Fallback is a YAML edit, not new code

### Negative consequences (trade-offs)

- Slightly larger `agentforge-core` than a minimum-viable framework
- `BudgetPolicy.check()` adds a small per-iteration cost (negligible,
  benchmarked)
- Default budget ($1.0) may surprise users running expensive workloads —
  documented loudly

## 5. Pros and cons of the options

### Option 1: Per-agent

- + Maximum flexibility per team
- − Drift; incidents repeated per team

### Option 2: Optional middleware

- + Opt-in keeps surface small
- − Loud-defaults principle (P6) violated; new agents will skip the
  middleware and get bitten

### Option 3: Framework-owned (chosen)

- + Loud defaults; uniform behaviour
- + Cross-cutting features (e.g. observability via run_id) compose
- − Slightly more in core

### Option 4: External service

- + Centralised
- − Adds infra; out of scope for an in-process framework

## 6. References

- [`docs/design/design-principles.md`](../design/design-principles.md) — P3, P4, P6
- [`docs/features/feat-007-production-rails.md`](../features/feat-007-production-rails.md)
- Archived: `docs/archive/cr/CR-008-cross-provider-fallback.md`,
  `CR-010-run-id-context-propagation.md`,
  `CR-013-idempotency-keys.md`
