# ADR-0007: ABC + Protocol contracts as the framework's stable surface

## Metadata

| Field | Value |
|---|---|
| **Number** | 0007 |
| **Title** | ABC + Protocol contracts as the framework's stable surface |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, contracts |

---

## 1. Context and problem statement

For a plug-and-play framework, *something* must be the stable thing that
modules implement and consumers depend on. Concrete classes are not it —
they evolve, they leak implementation details, they create inheritance
chains that break under refactoring. The framework needs an explicit
contract layer that is small, stable, and language-symmetric.

How do we express the framework's stable surface in a way that is
enforceable, testable, and evolves on a known schedule?

## 2. Decision drivers

- Locked contracts allow modules to ship independently with confidence
- Conformance must be testable — every driver runs the same suite
- Contract evolution must follow strict semver (P1)
- Cross-language parity (ADR-0002) demands a contract definition that
  translates cleanly between Python and TypeScript
- Avoid inheritance hierarchies that lock implementation choices

## 3. Considered options

1. **Concrete classes as contracts** — `LLMClient` is a class with default
   methods; modules subclass and override
2. **ABC + Protocol (chosen)** — abstract methods (`LLMClient`,
   `MemoryStore`, etc.) define the locked surface; concrete classes are
   reference implementations only
3. **Duck typing only** — no formal contracts; modules just expose the
   right method names
4. **Schema-driven (e.g. Pydantic models for everything)** — describe
   contracts as data; runtime checks against schema

## 4. Decision outcome

**Chosen: Option 2 — ABC + Protocol.**

Behavioural contracts (LLM client, memory store, reasoning strategy,
evaluator, validators, gates, embedding client) are `abc.ABC` in Python
with abstract methods. Structural contracts (Finding shape) are
`typing.Protocol` with `@runtime_checkable`. In TypeScript, both map
to `interface`. Modules implement; the framework consumes via the
abstract type. Reference implementations (`ReActLoop`, `InMemoryStore`,
`SimpleFinding`, etc.) ship in `agentforge` but live alongside the
abstractions, not inside them.

Conformance suites (per feat-016) run the same tests against every
driver — guaranteeing real conformance, not just type-checker happiness.

### Positive consequences

- Stable surface that modules can pin against
- Conformance tests enforce real behavioural compatibility
- Type-checker support out of the box (`mypy`, `tsc`) for misuse
- Cross-language translation is direct (ABC ↔ interface)

### Negative consequences (trade-offs)

- Slightly more code than concrete-class inheritance
- Protocol vs ABC distinction takes a few minutes to teach (we use ABC
  for behavioural; Protocol for structural-only contracts like Finding)
- Adding a method to an ABC is breaking — must be done with care

## 5. Pros and cons of the options

### Option 1: Concrete classes

- + Simple
- − Default implementations leak; modules accidentally inherit behaviour
- − Refactor risk: any change to the base ripples to all subclasses

### Option 2: ABC + Protocol (chosen)

- + Crisp separation of contract from implementation
- + Conformance testable
- + Maps to TS `interface` directly
- − Two abstraction kinds (ABC for behaviour, Protocol for shape) — small teaching cost

### Option 3: Duck typing only

- + Minimal ceremony
- − No formal contract; conformance impossible to verify
- − Type checkers can't help

### Option 4: Schema-driven

- + Contracts as data
- − Behaviour ≠ data; methods can't be expressed as schemas
- − Adds a runtime layer for what `mypy` already does

## 6. References

- [`docs/design/design-principles.md`](../design/design-principles.md) — P1 (contracts stable; implementations interchangeable), P10 (conformance enforced by tests)
- [`docs/design/architecture.md`](../design/architecture.md) §4
- [`docs/features/feat-001-core-contracts-and-agent.md`](../features/feat-001-core-contracts-and-agent.md)
- [`docs/features/feat-016-testing-framework.md`](../features/feat-016-testing-framework.md)
