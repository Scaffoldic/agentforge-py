# ADR-0012: `Finding` as Protocol with shipped variants

## Metadata

| Field | Value |
|---|---|
| **Number** | 0012 |
| **Title** | `Finding` as Protocol with shipped variants (not a single dataclass) |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, output |

---

## 1. Context and problem statement

Agents emit different shapes of output: code reviewers emit issues with
severity; patch bots emit diffs; Q&A agents emit prose with citations;
compliance sweeps emit multi-file findings. An earlier internal project used a
single `Finding` dataclass with 8 fixed fields, forcing patch and
narrative agents to misuse `metadata: dict[str, Any]` as an escape
hatch — defeating type safety and breaking downstream rendering.

How do we accommodate multiple output shapes without losing type safety
or breaking shared tooling (aggregators, dashboards)?

## 2. Decision drivers

- Agents have legitimately different output shapes
- Shared tooling (scorecards, aggregators) needs *some* common contract
- Type safety must survive variant choice
- Custom variants must be first-class
- Renderer dispatch must not require editing locked code

## 3. Considered options

1. **Single dataclass, escape via `metadata`** — the earlier internal shape
2. **Tagged union of fixed variants** — closed set of variant types
3. **Protocol (structural typing) + shipped variants + custom registration**
   — open set; minimum required attributes; custom variants implement
   the Protocol
4. **Tree of inheritance** — `Finding` base class, all variants subclass

## 4. Decision outcome

**Chosen: Option 3 — Protocol + shipped variants.**

`Finding` is a `runtime_checkable` `Protocol` requiring `severity`,
`category`, `message`, `to_dict()`. Shipped variants in `agentforge`:
`SimpleFinding`, `PatchFinding`, `NarrativeFinding`, `MultiSpanFinding`.
Custom variants are any class satisfying the Protocol — no inheritance
needed. A `RendererRegistry` dispatches per variant; agents register
custom renderers in their own code without touching framework code.

### Positive consequences

- Domain-appropriate findings without losing type safety
- Custom variants are first-class
- `metadata` is no longer a dumping ground
- Shared tooling stays compatible via the Protocol minimum

### Negative consequences (trade-offs)

- More types to know about (mitigated by runbook 11)
- Renderer registry adds a small dispatch layer
- Dashboards parsing variant-specific fields must handle absence

## 5. Pros and cons of the options

### Option 1: Single dataclass

- + Simplest
- − `metadata` becomes a black hole of typed-but-not-typed data

### Option 2: Tagged union

- + Closed; type checker exhaustively checks
- − Custom variants require editing the union (closed-for-extension)

### Option 3: Protocol + variants (chosen)

- + Open for extension; closed for the *contract*
- + Domain-specific variants stay typed
- − Slightly more types to teach

### Option 4: Inheritance

- + Familiar OO pattern
- − Forces a base class; mixing with `@dataclass` is awkward
- − Subclass relationships obscure cross-variant comparison

## 6. References

- ADR-0007 (ABC + Protocol surface)
- [`docs/features/feat-008-findings-and-output-shapes.md`](../features/feat-008-findings-and-output-shapes.md)
- Archived: `docs/archive/cr/CR-005c-pluggable-output-shape.md`
