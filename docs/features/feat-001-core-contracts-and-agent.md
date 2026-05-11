# feat-001: Core contracts & `Agent` orchestrator

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-001 |
| **Title** | Core contracts & `Agent` orchestrator |
| **Status** | shipped (Python — `agentforge-py#1` merged 2026-05-09; TypeScript pending) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Shipped (Python)** | agentforge-py main @ 9ea1033 (PR #1) — 192 tests, 94.28% coverage on diff |
| **Target version** | 0.1.0 |
| **Languages** | both |
| **Module package(s)** | `agentforge-core`, `agentforge` |
| **Depends on** | none |
| **Blocks** | feat-002, feat-003, feat-004, feat-005, feat-006, feat-007, feat-008, feat-010, feat-012 |

---

## 1. Why this feature

A team building an agent today picks a framework and immediately faces a fork in
the road: every framework has a slightly different way of expressing "an agent is
a model + tools + a loop." LangChain has `AgentExecutor`. CrewAI has `Crew`.
Pydantic AI has `Agent`. AutoGen has `AssistantAgent`. None of these compose; if
you bet on one and it goes the wrong way, you rewrite.

The pain is not that there are too many frameworks — it is that **the contracts
between an agent and its parts (model, tool, loop, memory) are not stable enough
to swap one part without rewriting the others**. We have seen this in a predecessor project: even
inside a single team, reasoning strategy and `Finding` shape were too tightly
coupled, and a second agent's needs forced ABCs into the codebase after the fact.

A new agent author opens an editor and asks: "Where does my model go? Where do my
tools go? Where does my prompt go? How do I run a loop?" If the answer is
"depends on which combination of classes you've subclassed," the author is going
to spend a week reading internals before writing useful code.

## 2. Why it must ship as framework

This is the foundational feature. Every other feature plugs into it. If we don't
own the contracts:

- **Cross-cutting concerns leak.** Cost guardrails, run_id propagation,
  evaluation hooks all live in one place — the `Agent` orchestrator. If each
  agent writes its own orchestrator, those concerns get re-invented (or
  forgotten) in every codebase.
- **Modules can't compose.** A memory driver, a provider client, and a tool only
  compose because they all implement contracts that `Agent` understands. Without
  the framework owning the contracts, every module would have to integrate with
  every other module N×N.
- **Upgrades become impossible.** P8 (upgrade-safe by construction) demands a
  stable surface that derived agents can rely on. The contracts in this feature
  are *the* stable surface.
- **The plug-and-play promise dies.** "Pick your model, swap your memory, change
  your loop without rewriting" is only true if there is a single, stable seam
  for each of those things. That seam is `agentforge-core`.

The anti-pattern if we don't ship this: every derived agent invents its own
`Agent` class with subtly different lifecycle semantics, tools wired with
slightly different signatures, and zero shared tooling between agents. We
already saw the early stages of this in a predecessor project before CR-005a/b/c/d landed.

## 3. How derived agents benefit

- **Day 1 — three-line agent.** An agent author writes `Agent(model="...",
  tools=[...])` and gets a working agent. No subclassing, no orchestrator class
  to author, no wiring code. Compare to LangChain (~30 lines for an equivalent),
  AutoGen (~15 lines), even bare Strands (~3 lines but no production rails).
- **Day 30 — adding a module.** When the same agent later needs persistence, an
  evaluator, or MCP, the only code change is `Agent(memory=..., evaluators=...)`
  — same constructor, new keyword. The author's existing tool functions, prompt
  strings, and pipeline tasks are untouched.
- **Day 90 — debugging a regression.** Because every agent built on AgentForge
  has the same lifecycle, a runbook that says "look at `state.steps` and the
  `run_id` log filter" is universally applicable. Cross-agent debugging skills
  transfer.
- **Day 180 — framework upgrade.** The `Agent` constructor surface is locked and
  semver-stable. Bumping `agentforge` from 0.4 → 0.5 cannot break the call site
  unless the major version changes.
- **A team running 5+ agents.** Cross-cutting features (a new evaluator, a cost
  cap policy change, a new observability hook) can be deployed by a single
  config change across all agents — because every agent uses the same `Agent`
  class with the same hook points.

## 4. Feature specifications

### 4.1 User-facing experience

```python
# Python — the absolute minimum
from agentforge import Agent

agent = Agent(model="anthropic:claude-sonnet-4.7")
result = await agent.run("Say hello in three words.")
print(result.output)
```

```python
# Python — typical
from agentforge import Agent
from agentforge.tools import web_search, calculator

agent = Agent(
    model="anthropic:claude-sonnet-4.7",
    tools=[web_search, calculator],
    system_prompt="You are a careful research assistant.",
    budget_usd=2.00,
)
result = await agent.run("What is 17% of the population of Spain?")
print(result.output)
print(result.steps)        # full trace
print(result.cost_usd)     # actual cost
```

```typescript
// TypeScript
import { Agent } from 'agentforge';
import { webSearch, calculator } from 'agentforge/tools';

const agent = new Agent({
  model: 'anthropic:claude-sonnet-4.7',
  tools: [webSearch, calculator],
  systemPrompt: 'You are a careful research assistant.',
  budgetUsd: 2.00,
});

const result = await agent.run('What is 17% of the population of Spain?');
console.log(result.output);
console.log(result.steps);
console.log(result.costUsd);
```

### 4.2 Public API / contract

**`agentforge-core` — locked contracts:**

```python
# agentforge_core/contracts.py
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Protocol, runtime_checkable

class LLMClient(ABC):
    @abstractmethod
    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    async def close(self) -> None: ...

    def capabilities(self) -> set[str]:
        return set()

class Tool(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any: ...

class ReasoningStrategy(ABC):
    @abstractmethod
    async def run(self, state: AgentState) -> AgentState: ...

class MemoryStore(ABC):
    @abstractmethod
    async def put(self, claim: Claim) -> str: ...
    @abstractmethod
    async def get(self, claim_id: str) -> Claim | None: ...
    @abstractmethod
    async def query(self, **filters: Any) -> list[Claim]: ...
    @abstractmethod
    async def supersede(self, old_id: str, new_claim: Claim) -> str: ...
    @abstractmethod
    async def stream(self, **filters: Any) -> AsyncIterator[Claim]: ...
    @abstractmethod
    async def close(self) -> None: ...
    def capabilities(self) -> set[str]:
        return set()

class Evaluator(ABC):
    name: str

    @abstractmethod
    async def evaluate(self, finding: Finding, context: dict[str, Any]) -> EvalResult: ...

@runtime_checkable
class Finding(Protocol):
    severity: str        # "critical" | "warning" | "suggestion" | "info"
    category: str
    message: str
    def to_dict(self) -> dict[str, Any]: ...

# Value types
class AgentState(BaseModel):
    run_id: str
    task: str
    steps: list[Step]
    findings: list[Finding]
    metadata: dict[str, Any]

class RunResult(BaseModel):
    output: str | dict[str, Any]
    findings: list[Finding]
    steps: list[Step]
    cost_usd: float
    tokens_in: int
    tokens_out: int
    run_id: str
    duration_ms: int
```

**`agentforge` — the `Agent` orchestrator (locked constructor surface):**

```python
# agentforge/agent.py
class Agent:
    def __init__(
        self,
        *,
        model: str | LLMClient,                    # "anthropic:claude-sonnet-4.7" | typed instance
        tools: list[Tool | Callable] | None = None,
        strategy: str | ReasoningStrategy = "react",
        memory: MemoryStore | None = None,         # None = InMemoryStore
        evaluators: list[Evaluator] | None = None,
        system_prompt: str | None = None,
        budget_usd: float = 1.0,
        max_iterations: int = 25,
        on_step: Callable[[Step], None] | None = None,
        on_finish: Callable[[RunResult], None] | None = None,
        config_path: str | Path | None = None,     # default: ./agentforge.yaml if exists
    ) -> None: ...

    async def run(self, task: str, **kwargs: Any) -> RunResult: ...
    async def close(self) -> None: ...

    # Context manager
    async def __aenter__(self) -> "Agent": ...
    async def __aexit__(self, *exc: Any) -> None: ...
```

The constructor signature is the contract. Adding a kwarg with a default is a
minor bump; removing or renaming requires a major bump.

### 4.3 Internal mechanics

```
                    Agent.__init__(...)
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
         load config   resolve modules  validate
        (agentforge.yaml  (entry points)  (Pydantic)
         + kwargs)
                            │
                            ▼
                    Agent.run(task)
                            │
                            ▼
              ┌─── set run_id ContextVar ────┐
              │     attach RunIdFilter       │
              ▼                              │
        BudgetPolicy.start()                 │
              │                              │
              ▼                              │
    strategy.run(AgentState) ──── (loop) ────┤
              │                              │
              ▼                              │
       evaluators.run() ─── (if any) ────────┤
              │                              │
              ▼                              │
      on_finish(result) ─────────────────────┤
              │                              │
              ▼                              │
       return RunResult                      │
              │                              │
       Agent.close() ────────────────────────┘
```

Key invariants:
- `run_id` is set before any module sees the run.
- `BudgetPolicy` is checked by every strategy before every LLM call (enforced by
  conformance test on strategies — feat-002).
- `on_step` fires once per `Step` appended to state, regardless of strategy.
- `on_finish` fires exactly once.
- `Agent.close()` flushes all hooks and closes all module connections; safe to
  call multiple times; called automatically by the `async with` context manager.

### 4.4 Module packaging

- `agentforge-core` (this feature ships ABCs, value types, and the resolver).
- `agentforge` (this feature ships the `Agent` class and `RunResult` /
  `AgentState` / `Step` value types).
- Both packages are always installed. There is no "install AgentForge without
  the Agent class" path.

### 4.5 Configuration

`Agent` reads `./agentforge.yaml` if present (or path given via `config_path=`).
Constructor kwargs override file values. Env vars (`AGENTFORGE_*`) override
nothing — they are only used inside config files via `${VAR}` interpolation.

Minimum viable `agentforge.yaml`:

```yaml
# agentforge.yaml
agent:
  model: "anthropic:claude-sonnet-4.7"
  strategy: "react"
  budget_usd: 1.0
```

Extended (with modules):

```yaml
agent:
  model: "anthropic:claude-sonnet-4.7"
  strategy: "react"
  budget_usd: 5.0
  max_iterations: 50

modules:
  memory:
    driver: "sqlite"
    config:
      path: "./agent.db"
  evaluators:
    - faithfulness
    - geval:
        rubric: "correctness"

logging:
  level: "INFO"
```

Full schema specified in feat-012 (Configuration system).

## 5. Plug-and-play & upgrade story

Always installed. No add/remove flow. Upgrades follow strict semver on the
constructor signature: minor bumps may add kwargs (with safe defaults); major
bumps may remove or rename them.

When the framework upgrades and a new kwarg appears, derived agents get the new
default for free. If a derived agent wants to opt in, they add the kwarg to
their `Agent(...)` call. No managed code in the agent's repo to merge.

## 6. Cross-language parity

**Identical:**

- Constructor argument names (snake_case in Py, camelCase in TS — same
  semantics)
- The contracts in §4.2 (translated to TS interfaces)
- `RunResult` shape
- `agentforge.yaml` schema

**Allowed to differ:**

- Python uses `async def`; TS uses `async ... Promise<T>`
- Python's `ContextVar` for `run_id` ↔ TS's `AsyncLocalStorage`
- Pydantic models (Py) ↔ Zod schemas (TS); both validate the same shape

**Deferred in TS:** none. `Agent` ships in both languages at v0.1.

## 7. Test strategy

- **Unit:** every `Agent.__init__` argument validated; bad combos raise at
  construction (fail-at-startup, P11).
- **Integration:** end-to-end test with `MockLLMClient` (feat-016) — verifies
  full lifecycle including hooks, budget, run_id propagation.
- **Conformance:** none here directly. `Agent` consumes ABCs; the ABCs'
  conformance suites live in their respective feature docs (feat-002, -003,
  -004, -005, -006).
- **Cross-language:** identical test scenarios in `pytest` and `vitest`; output
  shape compared.
- **Example agents:** the six starter templates (feat-011) all instantiate
  `Agent` and are smoke-tested in CI.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Constructor surface grows unboundedly as features land | Hard cap: any new top-level kwarg requires a design doc justifying why it isn't a config-only setting |
| String identifier (`"anthropic:claude-sonnet-4.7"`) breaks if model id changes upstream | Treat the substring after `:` as opaque — pass through to provider; provider raises if invalid. Do not validate model ids in core. |
| `RunResult` shape becomes a dumping ground | Locked at v0.1; new fields require feature doc and minor bump |
| Sync vs async confusion (some users want a sync surface) | Provide `agent.run_sync()` as a thin `asyncio.run()` shim; mark "for notebooks/scripts only"; not part of the locked surface |
| TS naming: `agentforge` (flat) vs `@agentforge/core` (scoped) | **Decided 2026-05-09: scoped** — `@agentforge/core`, `@agentforge/runtime`, `@agentforge/anthropic`, `@agentforge/memory-postgres`, etc. PyPI stays flat (`agentforge`, `agentforge-anthropic`); the asymmetry is normal in 2026. |
| Should `Agent` be a class or a function (LangGraph's `create_react_agent` style)? | Class. Class lifecycle (`__aenter__`/`__aexit__`) maps to cleanup; functional factory loses that. Class with `tools=[...]` keyword is also more discoverable in IDEs. |

## 9. Out of scope

- A higher-level "agent of agents" wrapper. Multi-agent shapes are a strategy
  (feat-002), not a separate `Agent` class.
- A streaming-by-default API. Streaming is a capability flag (feat-003);
  `Agent.run()` returns a single `RunResult`. Streaming surface comes through a
  separate `agent.stream(...)` method, designed when its first real consumer
  appears.
- Multi-modal input/output beyond text. Images, audio, video belong in tools or
  in a future feature doc. Core stays text-first.
- A persistent agent (server-resident, like Letta). `Agent` is a per-process
  object; persistent agents are constructed by wrapping `Agent` at a higher
  layer (see feat-020 for the chat/conversational deployment shape).
- Multi-turn conversation state. `Agent.run()` is one-shot. Conversational
  agents are built by wrapping `Agent` with `ChatSession` (feat-020), which
  owns turn history, streaming, and session lifecycle without changing the
  `Agent` contract.

## 10. References

- [`architecture.md`](../design/architecture.md) §3, §4
- [`design-principles.md`](../design/design-principles.md) — P1, P2, P6, P7,
  P9, P11, P12
- [`module-system.md`](../design/module-system.md) — how modules attach to
  `Agent` via the resolver
- feat-002 (reasoning strategies) — consumes the `ReasoningStrategy` ABC
- feat-003 (LLM providers) — consumes the `LLMClient` ABC
- feat-004 (tools) — consumes the `Tool` ABC
- feat-007 (production rails) — wires `BudgetPolicy`, `run_id`, fallback into
  `Agent.run()`
- Prior art: Pydantic AI's `Agent` (closest match to this surface), Strands'
  `Agent` (close on minimum-viable line count)

---

## Implementation status

**Status: shipped (Python).** Landed as
[Scaffoldic/agentforge-py PR #1](https://github.com/Scaffoldic/agentforge-py/pull/1)
on `feat/001-core-contracts-and-agent`.

The shipped surface matches this spec: `agentforge-core` ships the
locked ABCs (`LLMClient`, `Tool`, `MemoryStore`, `Evaluator`,
`ReasoningStrategy`, `Finding` Protocol) plus the frozen value types
(`Claim`, `LLMResponse`, `Message`, `AgentState`, `Step`,
`RunResult`, etc.). `agentforge` ships the `Agent` orchestrator with
the locked constructor surface, `BudgetPolicy`, `RunContext` /
`run_id` propagation, and resolver-based provider lookup.

Adding optional kwargs to the `Agent` constructor is a minor bump
under ADR-0007. Two have shipped since: `retriever=` and
`graph_store=` — both added during feat-005 work.

TypeScript port pending.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented. When feat-011 (Copier scaffolding) and
feat-019 (runbook system) ship, this section is consumed by the
templating engine and rendered into scaffolded agent projects.

### How do I create the smallest working agent?

```python
from agentforge import Agent

async with Agent(model="bedrock:us.anthropic.claude-sonnet-4-5-20250929") as agent:
    result = await agent.run("Say hello in three words.")
    print(result.output)
```

`async with` is the recommended form — `__aexit__` calls
`agent.close()` for you, which flushes hooks and closes provider
connections. Calling `close()` twice is safe (idempotent).

### How do I cap cost or iterations?

`Agent` exposes two budget kwargs:

```python
agent = Agent(
    model="bedrock:...",
    budget_usd=2.0,
    max_iterations=25,
)
```

The `BudgetPolicy` is constructed internally from these (token cap
and error-streak cap default to the policy's own defaults — drop
to a typed `LLMClient` if you need them). Caps trip a
`BudgetExceeded` from inside the strategy loop, terminating the
run with `finish_reason="budget_exceeded"`. Token / cost / iteration
counters are visible on `result.cost_usd`, `result.tokens_in/out`,
and `len(result.steps)`.

### How do I read the full step trace after a run?

```python
result = await agent.run("…")
for step in result.steps:
    print(step.iteration, step.kind, step.cost_usd, step.duration_ms)
```

`Step.kind` is one of `"think"`, `"act"`, `"observe"`, `"finish"`
(see feat-002 for strategy-specific extensions).
`result.cost_usd` is the sum of per-step costs; `result.run_id` is
the ULID that ties this run to log lines (feat-007 Runbook covers
`RunIdFilter`).

### How do I hook into each step / final result?

```python
def log_step(step):
    print(f"[{step.iteration}] {step.kind} — ${step.cost_usd:.4f}")

def persist_result(result):
    db.save_run(result.run_id, result.output, result.cost_usd)

agent = Agent(
    model="bedrock:...",
    on_step=log_step,
    on_finish=persist_result,
)
```

`on_step` fires once per `Step` appended to `state.steps`,
regardless of strategy. `on_finish` fires exactly once at the end
of `run()`. Both hooks are synchronous — wrap heavy I/O in
`asyncio.create_task(...)` if you need to fire-and-forget.

### How do I read configuration from `agentforge.yaml`?

The constructor reads `./agentforge.yaml` automatically if present:

```yaml
agent:
  model: "bedrock:us.anthropic.claude-sonnet-4-5-20250929"
  strategy: "react"
  budget_usd: 5.0
```

```python
agent = Agent()  # all settings come from agentforge.yaml
```

Constructor kwargs override file values; env vars are only
expanded inside the YAML via `${VAR}` interpolation (full schema
ships with feat-012).

### How do I switch providers without changing code?

Pass the model string — the resolver picks the registered driver:

```python
agent = Agent(model="bedrock:anthropic.claude-sonnet-4-5-20250929")
# later: pip install agentforge-anthropic
agent = Agent(model="anthropic:claude-sonnet-4-5")
```

Or pass a constructed `LLMClient` instance for full control:

```python
from agentforge_bedrock import BedrockClient

client = BedrockClient(model="us.anthropic.claude-sonnet-4-5-20250929",
                      region="us-east-1")
agent = Agent(model=client)
```

### How do I run the agent synchronously (notebook / script)?

```python
agent = Agent(model="bedrock:...")
result = agent.run_sync("hello")
```

`run_sync()` is a thin `asyncio.run()` shim. Not part of the locked
surface — designed for notebooks and one-shot scripts. In any
async context, use `await agent.run(...)`.

### When should I NOT instantiate `Agent` directly?

- **Multi-turn chat sessions.** `Agent.run()` is one-shot. Build
  conversational agents on top of `Agent` via `ChatSession`
  (feat-020 — not yet shipped) which owns turn history and
  streaming.
- **Multi-agent orchestration.** Wrap `Agent` instances inside
  `MultiAgentSupervisor` (feat-002), not in a hand-rolled outer
  agent class.
- **Server-resident persistent agent.** `Agent` is per-process.
  For Letta-style residency, persist `Claim`s via `memory=` and
  reconstruct state on the next process; framework support comes
  with feat-020.
