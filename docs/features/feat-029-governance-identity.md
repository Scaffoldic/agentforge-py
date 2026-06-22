# feat-029: Governance — identity (`Principal` / `IdentityProvider`)

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-029 |
| **Title** | Governance pillar 1 — identity: `IdentityProvider` + the widened `Principal` |
| **Status** | implemented (not yet released) |
| **Owner** | kjoshi |
| **Created** | 2026-06-22 |
| **Target version** | 0.4 (foundation); registry/policy/audit follow on 0.5 |
| **Languages** | `python` (TS deferred) |
| **Module package(s)** | `agentforge-core` (contract + widened value), `agentforge-governance` (`local` driver) |
| **Depends on** | feat-014 (`auth` / `Principal`), feat-026 (config), ADR-0023 (epic architecture) |
| **Blocks** | registry / policy / audit (all reference a principal) |

---

## 1. Why this feature

The first pillar of the governance spine (ADR-0023): every agent — and the
tools / services it talks to — needs a **stable, portable identity** so every
action has a name. Without it there is nothing to attribute a registry entry,
a policy decision, or an audit event to. Identity is foundational: the other
three pillars all key on a principal, so it ships first.

## 2. Why it must ship as framework

- **Universal.** Every governed agent needs a verifiable identity; none of it
  is domain-specific.
- **Builds on what exists.** The framework already has a `Principal` value and
  an `AuthPolicy` contract (feat-014). Identity extends that surface rather
  than inventing a parallel one.
- **Hard to get right, vendor-neutral.** A stable id scheme, credential
  issue/verify/rotate, and mappings onto OIDC / SPIFFE / cloud IAM are
  framework concerns; the `local` driver makes the whole thing offline-testable.

### 2.5 Framework-level vs derived-agent-level

**Framework.** The `Principal` value, the `IdentityProvider` contract, the URN
id scheme, the offline `local` driver, the conformance suite, and (later) the
OIDC/SPIFFE/cloud mappings.

- **Derived-agent test:** a consumer can't make its agent's identity portable
  or verifiable from its own code without re-implementing issue/verify/rotate
  and an id scheme — framework work.
- **How it helps derived agents:** an agent declares *who it is* in config
  (`governance.identity`); the framework makes that a verifiable, stable
  `Principal` every other pillar can attribute to. Config, not code.

## 3. How derived agents benefit

```yaml
governance:
  identity:
    provider: local           # local | oidc | spiffe | aws-iam …
    name: invoice-reconciler
    owner: finance-platform
    attributes: { env: prod, region: eu-west-1 }
```

The framework issues the agent's principal
`agentforge:agent:local/invoice-reconciler@1` — stable across deploys,
portable, and ready to be referenced by the registry, scoped by policy, and
attributed in the audit log.

## 4. Design

### 4.1 The widened `Principal` (ADR-0023 decision 3)

`agentforge_core.values.auth.Principal` gains `kind: str = "agent"` and
`owner: str | None = None` (both defaulted → backward compatible); `metadata`
serves as the `attributes` bag. One `Principal` flows through both
`AuthPolicy.authenticate(...)` and `IdentityProvider`.

### 4.2 The `IdentityProvider` contract

```python
class IdentityProvider(ABC):
    async def issue(self, *, name: str, owner: str,
                    attributes: Mapping[str, str] | None = None) -> Principal: ...
    async def resolve(self, principal_id: str) -> Principal | None: ...
    async def verify(self, token: str) -> Principal: ...        # inbound: prove who's calling
    async def credential(self, principal: Principal) -> str: ... # outbound: prove who we are
    async def rotate(self, principal_id: str) -> Principal: ...
    def capabilities(self) -> set[str]: ...
```

`issue` is idempotent on `name` (stable id); `resolve` returns `None` for an
unknown id; `verify` raises `IdentityError` on an invalid credential; `rotate`
keeps the id but invalidates prior credentials. Locked per ADR-0007.

### 4.3 The id scheme

`agentforge:agent:<org>/<name>@<version>` — a URN, stable across deploys,
portable, with a version component a registry entry can pin to. Vendor drivers
map this onto OIDC subjects / SPIFFE IDs / IAM ARNs without the framework
depending on any of them.

### 4.4 The `local` driver

`agentforge_governance.identity.LocalIdentityProvider`: in-process,
deterministic, zero-dependency. Issues/resolves principals in memory and signs
credentials with per-principal HMAC; `rotate` swaps the secret so prior
credentials stop verifying. The identity analogue of the SQLite `MemoryStore`
— the whole pillar is testable offline with no cloud account.

### 4.5 Config + wiring

`governance.identity` (strict, `extra="forbid"`); `build_identity_from_config`
resolves the `identity_providers` driver, constructs it, and issues the
agent's principal when `name` + `owner` are set. The `local` provider
registers under `[project.entry-points."agentforge.identity_providers"]`.

## 5. Backward compatibility

Fully additive. Widening `Principal` with two defaulted fields keeps every
existing `Principal(id=…)` / `Principal(id=…, metadata=…)` call working and
`AuthPolicy.authenticate(...)` unchanged. No `governance:` block → no identity,
identical behaviour to today.

## 6. Test strategy

- `run_identity_conformance` (in core) — issue→resolve round-trip + idempotency,
  credential/verify round-trip, rotation invalidating old credentials, and the
  unknown/invalid paths — run against `LocalIdentityProvider`, offline.
- Driver units: URN scheme, idempotent issue, rotation, capabilities,
  `build_identity_from_config` resolving the entry point + issuing the principal.

## 7. Out of scope (this pillar)
- OIDC / SPIFFE / cloud-IAM drivers (map onto the same contract; later).
- Deep runtime stamping of the principal onto every step/tool call — lands with
  the audit pillar, which is what consumes it.
- TypeScript port.

## 8. Implementation status (Python)
**Status: implemented (not yet released).** Ships the widened `Principal`, the
`IdentityProvider` ABC + `IdentityError`, `run_identity_conformance`, the
`agentforge-governance` package with `LocalIdentityProvider`, the
`governance.identity` config block, and `build_identity_from_config`.
Remaining for the pillar's full value (later PRs): the `Agent(identity=)`
constructor kwarg + run-time principal stamping (best done alongside audit).

## 9. References
- ADR-0023 (governance epic architecture), feat-014 (`auth` / `Principal`),
  feat-026 (config). Registry / policy / audit specs follow.
