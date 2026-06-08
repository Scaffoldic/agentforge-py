# Design Doc: AgentForge design principles

## Metadata

| Field | Value |
|---|---|
| **Title** | AgentForge — design principles |
| **Status** | draft |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Last updated** | 2026-05-09 |
| **Supersedes** | none |
| **Superseded by** | none |
| **Related features** | all |

---

## 1. Context

A pluggable framework only works if every module follows the same contract. These
principles are the contract. They apply to **every** feature, **every** module, and
**every** PR. A change that violates a principle either fixes the principle in this
doc first, or it does not land.

The list is intentionally small. If we cannot fit a rule on one line and explain it
in one paragraph, it is not a principle, it is a guideline — guidelines live in
feature docs.

## 2. Goals

- A new contributor can read this doc once and understand why the codebase looks
  the way it does.
- A reviewer can reject a PR by pointing at a numbered principle.
- A future maintainer can reason about whether a proposed change is aligned without
  reading every prior decision.

## 3. Non-goals

- Code style. That is enforced by formatters and linters, not by review.
- Process. CR/RFC pipeline, branching, commit conventions belong in
  `CONTRIBUTING.md`.
- Architecture. The current shape lives in `architecture.md`; this doc is the
  *rules*, not the *map*.

## 4. The principles

### P1 — Contracts are stable; implementations are interchangeable

Every load-bearing primitive is an ABC (Python) or interface (TypeScript). At least
one reference implementation ships in `agentforge`; alternative implementations are
opt-in modules. Contracts evolve through deprecation cycles, never through silent
breakage. Implementations may iterate freely behind the contract.

### P2 — Modules are pip-installable, never scaffolded

A module is a separate package on PyPI / npm. It self-registers via entry points and
is configured through `agentforge.yaml`. Developers do not copy module source code
into their agent. The corollary: the developer-owned scaffold contains tools,
prompts, custom tasks, and configuration — never framework primitives.

### P3 — One LLM call costs USD; the framework knows it

A budget is checked before every LLM call. There is no "fire and forget" path. A
strategy that branches or parallelises pre-reserves budget so collective spend is
bounded. Cost is a first-class concern, not an observability concern.

### P4 — Every run has a `run_id`; every log line carries it

`run_id` is generated on agent construction, propagated through context-local
storage, and attached to every log line, every tool call, every claim record, every
external trace. There is no path to a log line without a `run_id`.

### P5 — Configuration is data; behaviour is code

`agentforge.yaml` selects modules and tunes their parameters. It does not define
behaviour through string-coded function names, dynamic imports of arbitrary paths,
or templated logic. If a config file can change what an agent fundamentally does,
that is a feature defect.

### P6 — Defaults are loud; opt-ins are quiet

Sensible defaults — ReAct, in-memory state, $1 budget, structured logs, run_id
filter — are wired the moment a developer constructs an `Agent`. Nothing requires
configuration to *start*. Specialisation requires configuration; getting started
does not.

### P7 — Type-safe at the seam

Every public API takes typed arguments and returns typed values: Pydantic models in
Python, Zod schemas / TS types in TypeScript. `Any` / `unknown` is reserved for
genuinely untyped boundaries (raw provider responses); never used to paper over
untyped internal code.

### P8 — Upgrade-safe by construction

A developer must be able to upgrade from a minor version of any module to the next
without rewriting their custom code. The framework's scaffolded boilerplate is
managed by `agentforge upgrade` (Copier-based); custom code is owned by the
developer and never touched. We do not break custom code on minor bumps.

### P9 — Cross-language parity at the contract layer, idiomatic at the surface

Contracts (P1) are identical in Python and TypeScript. Idioms diverge: Python uses
`async def` and `ContextVar`; TS uses promises and `AsyncLocalStorage`. We do not
force one language to feel like the other.

### P10 — Conformance is enforced by tests, not by trust

Every ABC ships with a conformance test suite. New drivers run the same tests. If a
test fails, the driver is non-conformant; we do not ship non-conformant drivers.
Tests live with the module, so they travel when the module is extracted.

### P11 — Fail at startup, not at runtime

Configuration errors, missing modules, schema violations, and invalid combinations
are detected at agent construction. Once `Agent(...)` returns, the runtime invariants
are guaranteed. We do not surface configuration errors as exceptions during a long
run.

### P12 — A primitive belongs in core only when two real consumers need it

`agentforge-core` is small. Speculative abstractions ("we might need this if X")
stay out. A primitive is promoted from a module to core only after at least two
consumers have implemented it independently and the contract has been validated by
real use.

## 5. Alternatives considered

| Option | Why we didn't pick it |
|---|---|
| Convention over contracts (no ABCs) | Fails P10; conformance becomes folklore |
| Plugin loading via dynamic Python paths | Fails P5; turns config into code |
| Implicit globals for `run_id` (module-level) | Fails P4 in async; loses correlation across `await` points |
| Letting modules patch core at runtime | Fails P1 and P11; impossible to reason about |

## 6. Migration / rollout

These are the rules at v0.1. Subsequent design docs may add principles (rare) or
refine wording (more common). A principle is never silently changed; the decision
log below records every revision.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Principles drift from the code over time | Every PR template prompts "which principle does this honour or change?" |
| Principles become aspirational marketing | Reviewers must be able to *cite* a principle to reject a PR; if they can't, the principle is too vague |
| Rules ossify when the project should still be discovering its shape | We are at v0.x; principles can be amended via design doc until 1.0 |

## 8. Open questions

1. Do we need a 13th principle on backward-compatibility windows for config file
   schemas (separate from P8 which covers code)? Likely yes once we have shipped a
   v0.x agent that survives to v0.y.
2. Should P6 ("defaults are loud") imply a maximum-zero-config bar — for example,
   the framework must always produce *some* output even with no LLM provider
   configured? Track once we have first user feedback.

## 9. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-09 | Initial 12 principles drafted | Carried forward from a predecessor project's 10 design principles plus P8/P9 made explicit for the multi-language, plug-and-play model |

## 10. References

- [`architecture.md`](./architecture.md)
- [`module-system.md`](./module-system.md)
- Archived predecessor principles at `docs/archive/` (superseded by this doc)
