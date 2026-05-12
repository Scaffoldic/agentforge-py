# feat-002: Reasoning strategies — ReAct + Plan-Execute + Tree-of-Thoughts + Multi-Agent

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-002 |
| **Title** | Reasoning strategies — ReAct, Plan-Execute, Tree-of-Thoughts, Multi-Agent (all stable from v0.1) |
| **Status** | shipped (Python — ReAct + Plan-Execute + ToT + Multi-Agent loops) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Last updated** | 2026-05-10 |
| **Target version** | 0.1 |
| **Languages** | both |
| **Module package(s)** | `agentforge` (all four ship in the runtime) |
| **Depends on** | feat-001 |
| **Blocks** | none |

---

## 1. Why this feature

An agent's loop shape is the single biggest determinant of its behaviour,
cost, and failure modes. A code reviewer that scans a PR file-by-file
(ReAct) is a different agent from one that drafts an upfront plan and
executes steps in parallel (Plan-Execute) — even with identical tools and
prompts. Most frameworks hardcode a single loop and you live with it; if
a different shape would suit your task better, you fork the framework or
shoehorn your problem into the wrong shape.

The pain we have seen: teams pick ReAct because the framework only ships
ReAct, then spend weeks paying for unnecessary history replay on tasks
that were inherently parallel. Or they invent ad-hoc multi-step
orchestration in tool code, defeating the framework's observability and
cost guardrails because the loop shape is no longer the framework's
business.

## 2. Why it must ship as framework

- **Cost safety must apply to every loop shape.** Pre-reservation of
  budget for branching/parallel strategies (ToT, Multi-Agent) is
  non-trivial; if every agent reinvents it, somebody gets it wrong and
  the production rails (feat-007) are bypassed.
- **Observability requires a uniform `state.steps` representation.**
  Different loops, same trace shape — debugging skills transfer across
  agents.
- **Strategy is a config decision, not a fork.** Switching ReAct →
  Plan-Execute must be a one-line `agentforge.yaml` change. That is only
  possible if `ReasoningStrategy` is a stable framework contract.
- **Without a framework-owned contract:** every team builds its own
  loop, cost guardrails are inconsistent, and "what does this agent do
  under the hood?" becomes per-team folklore.

## 3. How derived agents benefit

- **Pick a loop without writing one.** `Agent(strategy="react")`,
  `Agent(strategy="plan-execute")`. Switching is one keyword.
- **Try a different loop without rewriting tools.** Tools, prompts,
  memory, and config are loop-agnostic. The same tool catalogue works
  under any strategy.
- **Defer the deliberation question.** Start with ReAct (cheap, flexible).
  When the task profile changes — say, a code reviewer that grows into a
  multi-file refactor agent — switch to Plan-Execute via config; the
  rest of the codebase is untouched.
- **Get cost safety for free even on branching loops.** ToT branches
  and pre-reserves budget; Multi-Agent workers inherit the supervisor's
  *remaining* budget proportionally. Authors of custom strategies get
  this enforced by conformance tests.
- **Cross-agent debugging.** `state.steps` is uniform across strategies,
  so a runbook ("read the trace, find the first thought with no
  observation") works on every agent.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import Agent, ReActLoop, PlanExecuteLoop
from agentforge.strategies import TreeOfThoughts, MultiAgentSupervisor

# 1. Default — ReAct, by string
agent = Agent(model="anthropic:claude-sonnet-4.7", tools=[...], strategy="react")

# 2. Plan-Execute, by string with config
agent = Agent(
    model="...", tools=[...],
    strategy="plan-execute",
    strategy_config={"max_parallel_steps": 4, "replan_on_failure": True},
)

# 3. Tree-of-Thoughts, typed instance for full configuration
agent = Agent(
    model="...", tools=[...],
    strategy=TreeOfThoughts(
        branch_factor=3,
        depth=2,
        score_threshold=0.6,
        scorer="self",   # "self" = same model; "judge" = cheap-judge model
    ),
)

# 4. Multi-Agent Supervisor, typed instance
agent = Agent(
    model="...", tools=[...],
    strategy=MultiAgentSupervisor(
        worker_strategy="react",
        max_concurrent_workers=4,
        budget_split="proportional",   # "proportional" | "equal"
        aggregation="structured",      # "structured" | "synthesised"
    ),
)

# 5. Custom — register and use by string
from agentforge import register
@register("strategies", "my-loop")
class MyLoop(ReasoningStrategy):
    async def run(self, state): ...

agent = Agent(model="...", tools=[...], strategy="my-loop")
```

### 4.2 Public API / contract

```python
# agentforge_core/contracts/strategy.py — locked (already in feat-001)
class ReasoningStrategy(ABC):
    """Drives the agent from initial task to terminal state.

    INVARIANTS (enforced by the conformance suite):
      - Guardrails (BudgetPolicy.check) called before every LLM call.
      - State flows through one shared AgentState — no module globals.
      - Every reasoning step appended to state.steps.
      - Termination is one of: stop_reason="end_turn", max_iterations,
        BudgetExceeded, GuardrailViolation.
      - Branching strategies (ToT, MultiAgent) pre-reserve budget
        before fanning out.
    """
    @abstractmethod
    async def run(self, state: AgentState) -> AgentState: ...
```

**Shipped reference implementations (all stable in `agentforge`):**

| Class | Stability | Module | Cost shape | Step.kind values emitted |
|---|---|---|---|---|
| `ReActLoop` | **stable** | `agentforge` | 1 LLM call per iteration; tool calls in between | `think`, `act`, `observe` |
| `PlanExecuteLoop` | **stable** | `agentforge` | 1 plan + N parallel step LLM calls + 1 synthesis | `plan`, `act`, `observe`, `synthesize` |
| `TreeOfThoughts` | **stable** | `agentforge` | branch_factor × depth + scoring calls | `branch`, `think`, `observe`, `synthesize` |
| `MultiAgentSupervisor` | **stable** | `agentforge` | 1 supervisor + (workers × per-worker budget); workers inherit *remaining* budget | `delegate`, `observe`, `synthesize` |

**Constructor signatures (locked):**

```python
class ReActLoop(ReasoningStrategy):
    def __init__(
        self,
        *,
        max_iterations: int | None = None,    # default: from BudgetPolicy
        finish_on_no_tool_call: bool = True,  # modern: stop_reason="end_turn" finishes
    ) -> None: ...

class PlanExecuteLoop(ReasoningStrategy):
    def __init__(
        self,
        *,
        max_parallel_steps: int = 4,
        replan_on_failure: bool = True,
        max_replans: int = 1,
    ) -> None: ...

class TreeOfThoughts(ReasoningStrategy):
    def __init__(
        self,
        *,
        branch_factor: int = 3,
        depth: int = 2,
        score_threshold: float = 0.5,
        scorer: Literal["self", "judge"] = "self",
        beam_width: int | None = None,        # None = keep all above threshold
    ) -> None: ...

class MultiAgentSupervisor(ReasoningStrategy):
    def __init__(
        self,
        *,
        worker_strategy: str | ReasoningStrategy = "react",
        max_concurrent_workers: int = 4,
        budget_split: Literal["proportional", "equal"] = "proportional",
        aggregation: Literal["structured", "synthesised"] = "structured",
    ) -> None: ...
```

### 4.3 Internal mechanics

**Modern primitives all four use:**

- **Tool calls are structured.** ReAct does not parse text for tool
  invocations; it consumes the `tool_calls` list on `LLMResponse`.
- **Termination is signal-based, not magic-string-based.** ReAct stops
  when the LLM returns `stop_reason="end_turn"` with no tool calls
  (modern Anthropic / OpenAI tool-calling pattern). No special `finish`
  tool needed.
- **Plans are typed.** Plan-Execute returns a Pydantic `Plan` model
  with `steps: list[PlanStep(id, action, depends_on, params)]` — the
  framework validates the plan before execution.
- **Branches are bounded by pre-reservation.** ToT and Multi-Agent
  reserve `BudgetPolicy.usd` upfront for the worst-case fanout; if
  reservation fails the strategy degrades gracefully (lower
  branch_factor, fewer workers) with a warning.

**ReAct (stable default):**

```
   ┌──── BudgetPolicy.check() ──── before every LLM call ────┐
   │                                                          │
   ▼                                                          │
  THINK ── LLM call (with tools) ──> LLMResponse              │
   │                                                          │
   ▼                                                          │
   if response.stop_reason == "end_turn" and no tool_calls:   │
       record observe step + return                           │
   ▼                                                          │
   ACT ── for each tool_call: dispatch → observe ─────────────┘
```

**Plan-Execute (modern Plan-and-Solve):**

```
  PHASE 1 — PLAN
    LLM call with task + tool catalogue → typed Plan(steps=[...])
    Validate plan: every step.depends_on resolves to a prior id
    Reserve budget for N steps + synthesis call

  PHASE 2 — EXECUTE (topological batches)
    For each batch:
        BudgetPolicy.check()
        Run all steps in batch concurrently (subject to max_parallel_steps)
        On step failure: if replan_on_failure and replans < max: re-plan
                         else: surface as observe step

  PHASE 3 — SYNTHESIZE
    LLM call: observations[] → final answer
```

**Tree-of-Thoughts (beam-search style):**

```
  ROOT — task
    │
    ▼  (BudgetPolicy.reserve(branch_factor × depth × cost_per_call))
  GENERATE branch_factor candidate thoughts (one LLM call)
    │
    ▼
  SCORE each (one call per branch — `scorer="self"` reuses agent's LLM;
              `scorer="judge"` uses a cheaper judge model)
    │
    ▼
  PRUNE below score_threshold (or keep top beam_width)
    │
    ▼
  EXPAND survivors (recurse to depth)
    │
    ▼
  SYNTHESIZE the best leaf into the final answer
```

**Multi-Agent Supervisor:**

```
  SUPERVISOR
    LLM call: task → list[WorkerSpec(role, subtask, budget_pct)]
    Validate: sum(budget_pct) <= 1.0 (prevents over-allocation)
    Reserve total = sum(BudgetPolicy.remaining_usd × budget_pct)
    │
    ▼
  WORKERS (run concurrently, max_concurrent_workers)
    Each runs its own ReasoningStrategy (default ReAct).
    Worker's BudgetPolicy = inherited slice of supervisor's remaining.
    Worker findings appended to state.findings.
    │
    ▼
  AGGREGATION
    aggregation="structured": deserialize workers' findings into one
                              merged Pydantic result
    aggregation="synthesised": LLM call combines worker outputs into
                               a free-form synthesis
```

**Shared infrastructure (`_StrategyBase`):** every concrete strategy
inherits a small mixin with `_check_guardrails()`, `_record_step()`,
`_call_llm()` (which checks budget, calls LLM, records cost). The
conformance suite verifies via AST inspection that every strategy
class touches `_check_guardrails` inside its main loop.

### 4.4 Module packaging

All four ship in `agentforge`. Entry-point registrations:

```toml
[project.entry-points."agentforge.strategies"]
react = "agentforge.strategies:ReActLoop"
plan-execute = "agentforge.strategies:PlanExecuteLoop"
tot = "agentforge.strategies:TreeOfThoughts"
multi-agent = "agentforge.strategies:MultiAgentSupervisor"
```

Custom strategies live in user code; same registration pattern.

### 4.5 Configuration

```yaml
agent:
  strategy: "react"

# With parameters
agent:
  strategy:
    name: "plan-execute"
    config:
      max_parallel_steps: 4
      replan_on_failure: true
      max_replans: 1
```

Each shipped strategy ships a Pydantic config model; the resolver
validates at startup (P11).

## 5. Plug-and-play & upgrade story

Switching strategy mid-project: edit `agentforge.yaml`, rerun. No code
change. Constructor signatures are locked from v0.1; minor versions may
add kwargs with safe defaults.

## 6. Cross-language parity

All four strategies ship in both Python and TypeScript at v0.1. The
`ReasoningStrategy` contract is identical in both; concrete reference
impls translate per language.

## 7. Test strategy

- **Conformance suite** in `agentforge_core.testing.conformance` —
  shared `run_strategy_conformance(strategy_factory)`; every shipped
  strategy passes.
- **AST-introspection test:** every shipped strategy class contains a
  call to `self._check_guardrails(...)` inside its main loop.
- **Cost-accounting test:** for branching strategies, total cost ≤
  `BudgetPolicy.usd` across N synthetic runs (Hypothesis property).
- **Trace-shape snapshots:** lock `state.steps` shape per strategy
  against a fixed scripted-LLM scenario.
- **Per-strategy unit + integration tests** with `FakeLLMClient` (a
  local test helper; the full `MockLLMClient` ships in feat-016).
- **Live tests** marked `@pytest.mark.live` against Bedrock (real
  Claude via AWS Bedrock) land once feat-003 ships the Bedrock
  provider — they exercise each strategy end-to-end with a real model.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Locking four strategies' surfaces from v0.1 reduces flexibility for design improvements | Constructor kwargs are minimal and orthogonal; new behaviours land as new kwargs with safe defaults (minor bump). Anything that requires a breaking change goes through a deprecation cycle (P8). |
| Multi-Agent supervisor blows past cost cap collectively | Workers inherit a slice of *remaining* supervisor budget (proportional or equal); supervisor verifies `sum(budget_pct) <= 1.0`; conformance test enforces. |
| Custom strategy authors forget to call guardrails | AST conformance test fails CI; documented in runbook. |
| ToT scoring with the same model creates bias (model rates its own thoughts highly) | Default `scorer="self"` works for most cases; document recommendation to use `scorer="judge"` with a cheaper model for high-stakes deliberation; runbook example. |
| Plan-Execute replanning could loop indefinitely | `max_replans` (default 1); after exhaustion the strategy returns whatever it has. |
| Should we ship Peer-to-peer / Hierarchical multi-agent? | Deferred — open design questions on convergence and cost bounding; revisit when a real agent needs them. The shipped Supervisor handles the most common production pattern. |
| Will the strategies work without feat-003 (real LLM provider)? | Tests use a `FakeLLMClient` (local test helper). At runtime users supply their own `LLMClient` instance (typed) until feat-003 ships provider modules. Bedrock-based live tests added once feat-003 lands. |

## 9. Out of scope

- **Custom-DAG workflow engines** (LangGraph-style explicit graphs).
  The four loop shapes here are *reasoning* strategies; for arbitrary
  DAG orchestration use the pipeline (feat-015) underneath an `Agent`,
  or write a custom strategy.
- **Streaming output mid-step.** Strategies return when complete;
  mid-step streaming is a future capability handled by the LLM client
  (feat-003), not by `run()`.
- **Strategy mixing within a single run** (e.g. ReAct that delegates
  to Plan-Execute for sub-tasks). Achievable today via
  `MultiAgentSupervisor` with per-worker-strategy config; no separate
  primitive needed.
- **Reflexion-style self-improvement loops.** Not in scope for v0.1;
  evaluator + replanning combined could approximate it. Add as a fifth
  strategy if a real agent needs it.

## 10. References

- [`architecture.md`](../design/architecture.md) §5
- [`design-principles.md`](../design/design-principles.md) — P1, P3, P10
- [`adr/0008-pluggable-reasoning-strategy.md`](../adr/0008-pluggable-reasoning-strategy.md)
- feat-001 (`Agent` consumes `ReasoningStrategy`); shipped as PR #1 in agentforge-py.
- feat-007 (`BudgetPolicy` already integrated; `_StrategyBase._check_guardrails` calls it).
- Archived: `docs/archive/subsystem-reasoning-strategies.md`
- ReAct paper (Yao et al. 2022): https://arxiv.org/abs/2210.03629
- Plan-and-Solve paper (Wang et al. 2023): https://arxiv.org/abs/2305.04091
- Tree of Thoughts paper (Yao et al. 2023): https://arxiv.org/abs/2305.10601
- Anthropic — *Building effective agents* (2024): https://www.anthropic.com/research/building-effective-agents

---

## Implementation status

**Status: shipped (Python).** Landed as
[Scaffoldic/agentforge-py PR #3](https://github.com/Scaffoldic/agentforge-py/pull/3)
on `feat/002-reasoning-strategies`.

All four strategies ship in `agentforge.strategies`:

- `ReActLoop` — observe / think / act / iterate.
- `PlanExecuteLoop` — plan once, execute steps; replan on guardrail
  trip.
- `TreeOfThoughts` — branching exploration with pluggable scorer.
  feat-006 shipped the post-run evaluator surface, but ToT's
  in-strategy `scorer="judge"` still calls `Agent.model` (same
  model, separate calls). Wiring a dedicated judge provider for
  ToT branch scoring is a follow-up; the named-provider config
  block from feat-003 makes that a small change when needed.
- `MultiAgentSupervisor` — delegate / execute workers / aggregate, with
  proportional budget split via `BudgetPolicy.remaining_usd() /
  n_workers`.

Every strategy passes `run_strategy_conformance` (locked invariants:
returns the same `AgentState`, monotonic `step.iteration`, valid
`StepKind`, non-negative cost/token/duration). Strategy lookup uses
the resolver from feat-001; e.g. `Agent(strategy="multi-agent")`.

TypeScript port pending.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented "how do I…" content. This is the canonical
home for the feature's runbook; feat-011 / feat-019 consume these
sections into scaffolded agent projects.

### How do I pick a strategy?

| If your task is… | Use |
|---|---|
| Tool-driven, iterative (search → read → answer) | `react` (default) |
| Decomposable up front (write 5 sections of a report) | `plan-execute` |
| Open-ended, "explore several paths" (hard math, planning) | `tot` |
| A team of specialists collaborating | `multi-agent` |

Strings resolve via the resolver — no import needed:

```python
agent = Agent(model="bedrock:...", strategy="plan-execute")
```

Pass a constructed strategy when you need to tune its kwargs:

```python
from agentforge.strategies import PlanExecuteLoop

agent = Agent(
    model="bedrock:...",
    strategy=PlanExecuteLoop(max_parallel_steps=8, max_replans=2),
)
```

### How do I tune ReAct?

ReAct has one knob — iteration cap, which the strategy reads from
`Agent.max_iterations` unless you override it on the strategy:

```python
from agentforge.strategies import ReActLoop

agent = Agent(
    model="bedrock:...",
    strategy=ReActLoop(max_iterations=10),  # tight cap for cheap loops
    tools=[web_search, calculator],
)
```

Leave `max_iterations=None` to honour the `Agent` budget's cap (the
common case). The strategy `_check_guardrails` runs before every
LLM call — `BudgetExceeded` short-circuits the loop cleanly.

### How do I use Plan-Execute with replanning?

`PlanExecuteLoop` plans once, executes in parallel batches, then
optionally replans on tool failure:

```python
from agentforge.strategies import PlanExecuteLoop

agent = Agent(
    model="bedrock:...",
    strategy=PlanExecuteLoop(
        max_parallel_steps=4,    # batch size for independent steps
        replan_on_failure=True,
        max_replans=1,           # one replan, then give up
    ),
)
```

After a tool raises, the supervisor LLM is asked to revise the
plan with the failed step's error in context. After `max_replans`
exhausted, the strategy returns whatever it has — the run does
NOT raise on tool failure.

### How do I use Tree-of-Thoughts with a cheaper judge?

Default `scorer="self"` makes the same model rate its own thoughts
— biased toward agreement. For high-stakes deliberation, pass
`scorer="judge"` and switch to a cheaper judge model:

```python
from agentforge.strategies import TreeOfThoughts

agent = Agent(
    model="bedrock:us.anthropic.claude-sonnet-4-5-20250929",
    strategy=TreeOfThoughts(
        branch_factor=3,
        depth=2,
        scorer="judge",     # uses a separate judge LLM
        score_threshold=0.7,
    ),
)
```

**Note:** feat-006 shipped the post-run evaluator surface
(`Correctness`, `Faithfulness`, etc.), but ToT's *in-strategy*
`scorer="judge"` still calls `Agent.model` for branch scoring —
same model, separate calls. Wiring ToT branch scoring to a
dedicated judge provider (the feat-003 named-provider mechanism)
is a small follow-up; for now, use a model-level fallback or
constrain `branch_factor` to keep judge cost bounded.

### How do I delegate to specialist workers?

`MultiAgentSupervisor` partitions a task across named workers,
each with its own strategy:

```python
from agentforge.strategies import MultiAgentSupervisor, ReActLoop, PlanExecuteLoop

agent = Agent(
    model="bedrock:...",
    strategy=MultiAgentSupervisor(
        workers={
            "researcher": ReActLoop(max_iterations=15),
            "writer": PlanExecuteLoop(max_parallel_steps=2),
        },
        worker_descriptions={
            "researcher": "Web search + reading; gathers facts.",
            "writer": "Drafts long-form output from collected notes.",
        },
        max_parallel_workers=2,
        max_rounds=1,
    ),
)
```

**Budget split:** each worker gets a slice of *remaining*
supervisor budget (proportional to `1 / n_workers`). If you set
`budget_usd=$5.00` and run 2 workers, each starts with ~$2.50; the
supervisor enforces the cap centrally.

### How do I read what each step did?

Every strategy emits the same `Step` shape — read `result.steps`:

```python
result = await agent.run("…")
for step in result.steps:
    print(step.iteration, step.kind, step.content[:80])
```

`step.kind` is one of `"think" | "act" | "observe" | "finish"` for
ReAct/Plan-Execute; ToT adds `"branch"` and `"score"`;
MultiAgentSupervisor nests sub-agent steps via
`step.metadata["worker"]`.

### When should I NOT use these strategies?

- **Custom DAG orchestration.** If your shape is a fixed pipeline
  (not LLM-driven), use feat-015 (Pipeline & tasks) underneath an
  `Agent`, not a strategy.
- **Streaming-during-step responses.** Strategies return when the
  step is done. Mid-step streaming is a provider capability
  (feat-003), surfaced through a separate `agent.stream(...)`
  method (not yet shipped).
- **Reflexion / self-improvement loops.** Not a shipped strategy.
  Approximate it via an `Evaluator` + `PlanExecuteLoop` replanning
  if needed; promote to a fifth strategy once a real agent
  demands it.
