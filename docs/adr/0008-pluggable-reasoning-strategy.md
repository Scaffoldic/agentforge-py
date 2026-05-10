# ADR-0008: Pluggable reasoning strategy ABC

## Metadata

| Field | Value |
|---|---|
| **Number** | 0008 |
| **Title** | Pluggable reasoning strategy ABC |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, reasoning |

---

## 1. Context and problem statement

Most frameworks hardcode one agent loop shape. ReAct works for many
tasks; Plan-Execute is cheaper for parallelisable work; Tree-of-Thoughts
is appropriate when multiple plausible paths must be compared;
Multi-Agent Supervisor is the right shape for parallel decomposition.
Locking the loop shape forces awkward fits when the task profile
doesn't match.

How do we let agents pick (or experiment with) different reasoning
loops without forking the framework or rewriting tools?

## 2. Decision drivers

- One agent's "best loop" is another agent's "wrong tool"
- Cost guardrails (ADR-0010) must apply uniformly regardless of loop
  shape
- Trace shape (`state.steps`) must stay uniform so debugging skills
  transfer across agents
- Custom strategies must be possible without forking
- Loop swap must be a config edit, not a code change

## 3. Considered options

1. **Hardcoded ReAct** — what most agent frameworks do at the start
2. **`ReasoningStrategy` ABC** with shipped reference implementations,
   custom strategies pluggable
3. **DAG / workflow engine** — build everything on a generic graph
   primitive (LangGraph approach)
4. **Per-step plugin chain** — pluggable thinker, actor, observer

## 4. Decision outcome

**Chosen: Option 2 — `ReasoningStrategy` ABC.**

`ReasoningStrategy.run(state) -> state` is the locked contract. Shipped
implementations: `ReActLoop` (stable), `PlanExecuteLoop`,
`TreeOfThoughts`, `MultiAgentSupervisor` (experimental). Strategies
must honour invariants enforced by conformance tests: guardrails called
before every LLM call, all state through `AgentState`, every step
recorded in `state.steps`, deterministic termination.

Custom strategies live in agent code or a shared package and register
via the same entry-point mechanism (ADR-0004). The Agent picks a
strategy by config: `agent.strategy: "react"`. Switching is one line
of YAML.

### Positive consequences

- Agents can pick the right loop without forking
- Strategies are interchangeable at config time
- Custom strategies are first-class (not a hack)
- Conformance tests guarantee cost / observability invariants regardless
  of loop choice

### Negative consequences (trade-offs)

- More code to understand (4 strategies vs 1)
- Experimental strategies (`PlanExecute`, `ToT`, `Multi-Agent`) need
  stability markers until APIs settle
- Conformance test for guardrail-call ordering uses AST introspection —
  a small piece of meta-programming

## 5. Pros and cons of the options

### Option 1: Hardcoded ReAct

- + Simple
- − Agents with non-ReAct shapes fork the framework

### Option 2: ABC + reference impls (chosen)

- + Pluggable; conformance-enforced
- + Strategy is a config decision
- − Multiple shipped impls to maintain

### Option 3: DAG / workflow engine

- + Maximum flexibility
- − Programming-by-graph is verbose for the common case
- − Doesn't compose with the simple "tools + prompt" mental model

### Option 4: Per-step plugin chain

- + Modular at finer grain
- − Cross-cutting concerns (cost, error streak) become hard to enforce
- − No clear conformance story

## 6. References

- ADR-0007 (ABC + Protocol surface)
- ADR-0010 (production rails)
- [`docs/features/feat-002-reasoning-strategies.md`](../features/feat-002-reasoning-strategies.md)
- Archived: `docs/archive/cr/CR-005d-i-reasoning-strategy-abc.md`
