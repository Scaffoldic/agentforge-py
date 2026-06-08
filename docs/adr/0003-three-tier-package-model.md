# ADR-0003: Three-tier package model (core / runtime / modules)

## Metadata

| Field | Value |
|---|---|
| **Number** | 0003 |
| **Title** | Three-tier package model (core / runtime / modules) |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, packaging |

---

## 1. Context and problem statement

A framework distributed as a single mega-package
pulls in every provider SDK at install time, balloons dependencies, and
slows imports. Distributing as a thousand independently-versioned packages
creates version-matrix hell where any minor
core bump can break long-tail integrations.

How do we structure the framework's pip / npm packages so that a developer
installs only what they use, contracts stay stable, and version skew is
bounded?

## 2. Decision drivers

- A "hello world" must be one `pip install` and three lines of code
- Adding a capability (memory, MCP, observability) must be a `pip install`
  and a YAML edit — never a major rewrite
- The set of stable contracts (ABCs) must live in one place so every module
  can pin to them with confidence
- We must avoid the version-matrix sprawl of fully-decomposed packaging
- We must avoid the "everything in one tin" install bloat of a single mega-package

## 3. Considered options

1. **One mega-package** — `agentforge` includes everything (single mega-package model)
2. **Single package + extras** — `agentforge[anthropic,postgres,...]` extras pull in providers (single-package-plus-extras model)
3. **Three-tier split** — `agentforge-core` (ABCs) + `agentforge` (defaults runtime) + `agentforge-<X>` (modules)
4. **Fully decomposed** — every primitive in its own package (fully-decomposed model, ~300 packages)

## 4. Decision outcome

**Chosen: Option 3 — Three-tier split** (with extras as a *convenience layer*
on top of the split).

`agentforge-core` ships only ABCs, value types, and the resolver — no I/O,
no SDKs. `agentforge` ships defaults: ReAct loop, in-memory store, four
default tools, simple findings, safety basics. `agentforge-<X>` packages
ship every other module (providers, persistence drivers, MCP, observability,
guardrails, evaluators, chat). This is the same shape adopted by other
production agent frameworks that split a core contract package from a
defaults runtime and an extensions tier — a shape that proved cleaner than
their single-package or fully-decomposed predecessors.

We layer pip extras (`agentforge[anthropic]`) on top as a discoverability
sugar: the extra installs the underlying `agentforge-anthropic` package.

### Positive consequences

- "Hello world" pulls in only `agentforge-core` + `agentforge` (~5 deps)
- Adding a capability is one extra install
- Provider modules version independently from the core contract
- Static inspectability via entry points (per ADR-0004)

### Negative consequences (trade-offs)

- Three-tier split means three release artefacts to coordinate (mitigated by
  ADR-0015 coordinated release train)
- Users must learn that `agentforge-core` and `agentforge` are different
  packages
- Documentation must constantly reinforce which tier owns what

## 5. Pros and cons of the options

### Option 1: One mega-package

- + Simplest install
- − Pulls in every SDK; bloated; hostile to security-conscious deploys

### Option 2: Single package + extras

- + Discoverable
- − No clean boundary between contracts and implementations
- − Custom modules can't pin only to the contract layer

### Option 3: Three-tier split (chosen)

- + Clear boundary: contracts (locked) / runtime (defaults) / modules (opt-in)
- + Modules pin to `agentforge-core` major; can iterate freely
- − Three artefacts to release; coordinated via ADR-0015

### Option 4: Fully decomposed

- + Maximum granularity
- − Fully-decomposed packaging demonstrated the matrix-hell pattern; minor core bumps break long-tail integrations regularly

## 6. References

- ADR-0004 (module discovery via entry points)
- ADR-0015 (coordinated release train)
- [`docs/design/architecture.md`](../design/architecture.md) §5
- Prior art: comparable production agent frameworks with a tiered package model
