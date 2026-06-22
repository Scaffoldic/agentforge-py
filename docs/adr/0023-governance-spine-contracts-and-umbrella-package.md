# ADR-0023: Governance spine — locked contracts in core, one umbrella driver package

## Metadata

| Field | Value |
|---|---|
| **Number** | 0023 |
| **Title** | Governance spine — locked contracts in core, one umbrella driver package |
| **Status** | Accepted |
| **Date** | 2026-06-22 |
| **Deciders** | kjoshi |
| **Tags** | architecture, governance, contracts |

---

## 1. Context and problem statement

The framework assembles agents (providers, memory, RAG, MCP/A2A, eval,
guardrails, budgets). It does not yet give an operator the means to *govern*
a fleet of those agents: a stable identity per agent, an inventory of what
each agent is, enforceable rules over what it may do, and a tamper-evident
record of what it did. These four concerns — **identity, registry, policy,
audit** — are universal production needs (every org running agents needs
them) and are load-bearing/hard to get right, so they belong in the
framework, not re-implemented per agent.

This ADR fixes the architecture for the whole governance epic (feat-029
identity, and the registry/policy/audit features that follow). Each pillar
introduces a **new locked core contract**, so the cross-cutting decisions —
where the contracts live, how the drivers are packaged, and how identity
relates to the existing `auth` `Principal` — must be settled once, here.

## 2. Decision drivers

- **Contracts-and-drivers** (the framework's universal rule, ADR-0003/0007):
  a locked ABC in `agentforge-core` + swappable drivers discovered via entry
  points.
- **Offline-first**: every pillar must be deterministically testable with no
  network and no cloud account (file/sqlite drivers ship first).
- **Vendor-neutral by construction**: native primitives that *map onto*
  OIDC / SPIFFE / cloud IAM / OPA / SIEM, never a hard dependency on one.
- **Additive, not a rewrite**: build on what exists (`auth`, config spine,
  observability, budgets, persistence) — minor bumps, no breakage.

## 3. Decisions

1. **The four contracts live in `agentforge-core`.** `IdentityProvider`
   (feat-029), `Registry`, `PolicyEngine`, and `AuditSink` are locked ABCs in
   `agentforge_core.contracts`, each with a conformance suite in
   `agentforge_core.testing`, exactly like `MemoryStore` / `GraphStore`.

2. **Default drivers ship in ONE umbrella package, `agentforge-governance`.**
   Rather than four micro-packages (`agentforge-identity`, `-registry`,
   `-policy`, `-audit`), the offline default drivers (`local` identity, file /
   sqlite registry, native policy, jsonl / sqlite audit) live in a single
   package with one dependency surface. The pillars are tightly related and
   usually adopted together; one package is a simpler install and release unit.
   Heavier vendor drivers (OIDC, OPA, SIEM, postgres) may still ship as their
   own packages later. The contracts stay in core regardless.

3. **Identity reuses the existing `Principal`, widened additively.** feat-014
   already ships `agentforge_core.values.auth.Principal` (`id` + `metadata`).
   Rather than introduce a second, colliding `Principal`, we **widen** it with
   `kind: str = "agent"` and `owner: str | None = None` (both defaulted →
   backward compatible), and treat `metadata` as the governance `attributes`
   bag. One `Principal` flows through both `AuthPolicy.authenticate(...)` and
   `IdentityProvider`. This resolves the identity draft's open question and
   keeps `auth` working unchanged.

4. **New entry-point categories**, resolved automatically by the existing
   resolver: `agentforge.identity_providers`, `agentforge.registries`,
   `agentforge.policy_engines`, `agentforge.audit_sinks`.

5. **Config under a reserved `governance:` block**, strict (`extra="forbid"`)
   like the rest of config, with `identity` / `registry` / `policy` / `audit`
   sub-blocks added as each pillar lands.

6. **Build-dependency order: Identity → Registry → Policy → Audit.** Identity
   is foundational (the other three reference a principal); Audit ships last
   (it records identity-attributed policy decisions). Each pillar is its own
   `feat-NNN` + ships on the coordinated release train (ADR-0015).

## 4. Consequences

- **Positive:** one coherent spine; consumers turn governance on by config;
  the contracts are swap-compatible (file/sqlite today, cloud later); no
  breaking change to `auth`; each pillar is independently reviewable.
- **Negative / trade-offs:** the umbrella package couples the four drivers'
  release cadence (acceptable — they version in lockstep anyway); widening
  `Principal` adds two fields to a locked value type (a minor bump, but it is a
  locked-surface change recorded here).
- **Deferred to the per-pillar specs:** policy rule-precedence + fail-mode,
  audit tamper-evidence strength, the registry `RegistryDiff` shape, and
  whether a dedicated `CheckpointStore`-style ABC is ever needed.

## 5. References

- feat-029 (identity, the first pillar) and the registry/policy/audit specs.
- ADR-0003 (modules as entry points), ADR-0007 (locked surfaces),
  ADR-0015 (coordinated release train).
- Builds on: feat-014 (`auth` / `Principal`), feat-026 (config spine),
  feat-007 (budgets), feat-009 (observability), feat-005/024 (persistence).
