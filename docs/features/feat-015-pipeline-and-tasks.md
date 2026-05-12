# feat-015: Pipeline & deterministic tasks

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-015 |
| **Title** | Pipeline — `Pipeline` engine, `Task` ABC, deterministic dimension-of-analysis tasks |
| **Status** | shipped |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.2 |
| **Languages** | both |
| **Module package(s)** | `agentforge` |
| **Depends on** | feat-001, feat-008 |
| **Blocks** | none |

---

## 1. Why this feature

Not every analysis an agent does should be free-form LLM reasoning. A code
reviewer running coverage checks, lint, dependency-graph traversal, and
import-cycle detection across a PR is doing four deterministic analyses —
each cheap, each predictable, each producing structured findings. Wrapping
those in LLM reasoning is wasteful and unpredictable.

The pattern: a deterministic pipeline of typed `Task`s runs in parallel,
emits findings, then the LLM agent reasons *over* those findings. The
agent's job becomes orchestration and judgement, not raw analysis. This is
exactly what good code review tools do — and most agent frameworks don't
support it cleanly.

## 2. Why it must ship as framework

- **A common Pipeline engine** with Finding output guarantees that
  deterministic tasks compose with LLM reasoning. Without it, every agent
  hand-rolls execution + parallelism + error-handling + finding aggregation.
- **Cost predictability.** Pipeline tasks are deterministic; their cost is
  not LLM-bound. Framework-owned pipeline lets us subtract pipeline runtime
  from the LLM budget.
- **Cross-agent task reuse.** A `coverage_task` is a `Task` subclass; any
  agent can use it. Without a framework `Task` ABC, every agent invents
  its own task shape.
- **Without framework ownership:** ad-hoc threading, inconsistent error
  handling, no cross-task finding aggregation.

## 3. How derived agents benefit

- **Add a deterministic dimension in 30 lines.** Subclass `Task`,
  implement `run()`, return findings.
- **Free parallelism.** Pipeline runs independent tasks in parallel,
  honouring `max_concurrent`.
- **Cost-bounded.** Tasks declare `cost_estimate_usd: 0` (most tasks); the
  agent's budget budget covers any LLM-using tasks separately.
- **Integrated reporting.** Pipeline output feeds `RendererRegistry`
  (feat-008); the same scorecard / patch / narrative renderer renders both
  task and agent findings.
- **Agent reasons over pipeline output.** Use cases like "the pipeline found
  these 12 issues; pick the top 3 to comment on" become natural.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import Agent, Pipeline, Task, SimpleFinding

class CoverageTask(Task):
    name = "coverage"
    cost_estimate_usd = 0.0

    async def run(self, context: dict) -> list[Finding]:
        cov = await run_coverage(context["repo_path"])
        return [
            SimpleFinding(
                severity="warning" if cov < 0.7 else "info",
                category="coverage",
                message=f"Coverage at {cov:.0%}",
            )
        ]

class LintTask(Task):
    name = "lint"
    async def run(self, context):
        result = await run_ruff(context["repo_path"])
        return [SimpleFinding(severity="warning", category="lint",
                              message=f"{r.message}", file=r.file, line=r.line)
                for r in result]

pipeline = Pipeline([CoverageTask(), LintTask()], max_concurrent=4)

agent = Agent(
    model="anthropic:claude-sonnet-4.7",
    tools=[...],
    pipeline=pipeline,
)

# Pipeline runs first; agent gets findings as a system-prompt addendum + tool
result = await agent.run("Review this PR", context={"repo_path": "./repo"})
```

### 4.2 Public API / contract

```python
# agentforge/pipeline/contracts.py — locked
class Task(ABC):
    name: str
    cost_estimate_usd: float = 0.0
    timeout_s: float = 60
    depends_on: list[str] = []

    @abstractmethod
    async def run(self, context: dict[str, Any]) -> list[Finding]: ...

class Pipeline:
    def __init__(
        self,
        tasks: list[Task],
        *,
        max_concurrent: int = 4,
        on_task_error: Literal["continue", "fail"] = "continue",
    ) -> None: ...

    async def run(self, context: dict[str, Any]) -> PipelineResult: ...

class PipelineResult(BaseModel):
    findings: list[Finding]
    task_durations_ms: dict[str, int]
    task_failures: dict[str, str]      # task_name → error message
    total_cost_usd: float
```

### 4.3 Internal mechanics

- Tasks resolved into a DAG by `depends_on`.
- Topological batches run in parallel up to `max_concurrent`.
- Each task gets the merged context (caller's + prior tasks' findings, if
  declared).
- Failures surfaced based on `on_task_error`; "continue" appends a special
  failure-Finding; "fail" raises.
- All findings consolidated into one `PipelineResult` with timing + cost.
- Pipeline output exposed to the agent via:
  - System prompt addendum: "Pipeline findings: [...]"
  - A built-in tool `pipeline_findings()` that the agent can re-query.

### 4.4 Module packaging

In `agentforge`. Tasks themselves live wherever the developer wants — in
the agent's own code or in `agentforge-tasks-*` shared packages.

### 4.5 Configuration

```yaml
pipeline:
  enabled: true
  max_concurrent: 4
  on_task_error: "continue"
  tasks:
    - "coverage"            # entry-point lookup or in-repo registration
    - "lint"
    - "security_scan":
        config:
          ruleset: "high"
```

## 5. Plug-and-play & upgrade story

Pipeline is part of `agentforge`; always available. Tasks ship as code or
as shareable packages (e.g. `agentforge-tasks-python` for Python-specific
analyses). Adding a task is the same module mechanism.

Upgrade: `Task` ABC locked. New shipped tasks ship with new versions; opt-in
by adding to the YAML.

## 6. Cross-language parity

Pipeline + Task ABC identical. Several built-in tasks ship per language as
ecosystems differ (Python's coverage tools ≠ TS's coverage tools).

## 7. Test strategy

- **Pipeline ordering:** dependent tasks see findings from their
  dependencies.
- **Parallelism honoured:** `max_concurrent` respected.
- **Failure isolation:** one task throwing doesn't crash others (when
  `on_task_error: continue`).
- **Cost accounting:** declared `cost_estimate_usd` matches actual when LLM
  involved.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Pipeline + agent dual orchestration confuses users | Document the pattern: pipeline is deterministic, agent is judgemental |
| Should pipeline be optional on `Agent`? | Yes — `pipeline=None` default. Many agents don't need it. |
| Streaming pipeline output to the agent mid-run | Defer — batch handoff is enough for v0.2 |
| Should tasks be allowed to call the LLM? | Yes — declare `cost_estimate_usd > 0`; framework checks budget reservation |
| Task name uniqueness across packages | Resolver checks at startup; conflicts are clean errors |

## 9. Out of scope

- A workflow DAG engine (Airflow / Prefect). Use one of those alongside if
  you need scheduling, retries, distributed execution.
- Cross-pipeline shared state. Each `Pipeline.run()` is self-contained.
- Long-running pipelines (hours+). Out of scope; the framework targets
  agent-run timescales (seconds to minutes).

## 10. Implementation status (Python)

Shipped in PR #25. Framework-only feature inside the main
`agentforge` package — no new sister packages.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `255f0f7` | `agentforge_core.contracts.task.Task` ABC + `agentforge_core.values.pipeline.PipelineResult` (frozen) + `FinishReason` literal extended with `"pipeline"` + `run_task_conformance` harness in `agentforge_core.testing`. |
| 2 | `ca03e27` | `agentforge.pipeline.Pipeline` engine: DAG validation (duplicate names / missing deps / cycles at construction), `asyncio.Semaphore`-bounded parallelism, per-task `asyncio.wait_for(timeout_s)`, `on_task_error` continue/fail. `PipelineFailure` exception + `register_task(name)` resolver helper. |
| 3 | `69298ca` | `PipelineFindingsTool` built-in tool + `Agent(pipeline=...)` kwarg + `Agent.run(task, *, context, replay_pipeline)` API. System-prompt addendum threaded per-run; `PipelineResult` recorded as `__pipeline` claim; `load_pipeline_result` for replay; `Agent.run` refactored under PLR0915. |
| 4 | `9782786` | `modules.pipeline:` config block (`PipelineConfig` + `PipelineTaskEntry`) + module-schema validation via the `tasks` resolver category + `build_pipeline_from_config` wired into `build_agent_from_config`. |
| 5 | `0586e3f` | Public re-exports (`agentforge.{Pipeline, Task, PipelineResult, PipelineFailure, PipelineFindingsTool, register_task}`) + renderer-compat sanity test against `RendererRegistry.default()`. |
| 6 | (this PR) | Docs + Runbook + roadmap + CHANGELOG + state. |

### Deviations from the design

- **`Agent.run(task, *, context=None, replay_pipeline=None)`.**
  The spec showed `agent.run(task, context={...})` only;
  shipped with an additional `replay_pipeline` keyword so the
  CLI's `--replay` path can short-circuit re-execution of
  side-effect-bearing tasks. Caller-facing surface for the
  common case is unchanged.
- **Pipeline failures use `finish_reason = "pipeline"`.** The
  `FinishReason` literal in `agentforge_core.values.state`
  gained a new entry. The feat-017 CLI maps it to generic exit 1
  (no separate exit code allocated; the exit-code surface stays
  stable).
- **Recording integration.** `agentforge.recording` exposes a
  new `PIPELINE_CATEGORY = "__pipeline"` reserved category +
  `record_pipeline_result(...)` helper alongside the feat-017
  step/eval/run categories. Replay reads the claim back via
  `agentforge.replay.load_pipeline_result`.
- **TypeScript port deferred.** The contract is locked; TS port
  lands with the TS scaffolding.

### Open items

- **Mid-run streaming pipeline output.** Spec §8 deferred this;
  no follow-up needed yet — batch handoff is sufficient for v0.2.
- **LLM-using tasks (`cost_estimate_usd > 0`).** The engine
  charges declared cost against the run budget; an end-to-end
  example wiring a `Task` to an `LLMClient` ships when the first
  real use case lands (likely the code-reviewer template).
- **Live integration test of `--replay` with a recorded
  pipeline.** Covered by unit tests today; a CLI-level smoke run
  will land with the next round of integration test work.

## 11. Runbook

### How do I add a deterministic task?

Subclass `Task`, declare the class attributes, implement
`async run(context) -> list[Finding]`:

```python
from collections.abc import Mapping
from typing import Any

from agentforge import SimpleFinding, Task
from agentforge_core.contracts.finding import Finding


class CoverageTask(Task):
    name = "coverage"
    cost_estimate_usd = 0.0
    timeout_s = 30.0
    depends_on = ()

    async def run(self, context: Mapping[str, Any]) -> list[Finding]:
        repo = context["repo_path"]
        pct = await measure_coverage(repo)  # your own helper
        return [SimpleFinding(
            severity="warning" if pct < 0.7 else "info",
            category="coverage",
            message=f"Coverage at {pct:.0%}",
        )]
```

Then build a `Pipeline` and pass it to the agent:

```python
from agentforge import Agent, Pipeline

pipeline = Pipeline([CoverageTask(), LintTask()], max_concurrent=4)
agent = Agent(
    model="anthropic:claude-sonnet-4-6",
    pipeline=pipeline,
    system_prompt="You are a code reviewer.",
)
result = await agent.run(
    "Review this PR",
    context={"repo_path": "./repo"},
)
```

The LLM sees the consolidated findings two ways: as a markdown
addendum on the system prompt, and via a built-in
`pipeline_findings(category=..., severity=...)` tool it can
re-query.

### How do I wire a pipeline from config?

Register your task class (entry point or
`@register_task("name")`) and list it in `agentforge.yaml`:

```yaml
modules:
  pipeline:
    enabled: true
    max_concurrent: 4
    on_task_error: continue        # or "fail"
    tasks:
      - name: coverage
      - name: lint
        config: {strict: true}
```

`agentforge config validate` checks both the schema shape and
each task's per-entry `config` against its `config_schema` (if
declared). `agentforge health` confirms the resolver finds every
referenced task.

### How do I debug a failing task?

On `on_task_error="continue"` (default), the engine emits a
`SimpleFinding(category="pipeline.task_failure",
rule_id=<task_name>)` for the offending task. The full
exception message lives in `PipelineResult.task_failures`. Use
`agentforge debug --replay <run-id>` to step through the
recorded run and inspect the cached findings via the
`pipeline_findings` tool.

On `on_task_error="fail"`, the engine cancels outstanding
runners and raises `PipelineFailure` (the agent run terminates
with `finish_reason = "pipeline"`).

### How does replay handle pipeline output?

`Agent(record_runs=memory)` persists each `PipelineResult` as a
single `__pipeline` claim. `agentforge run --replay <run-id>`
loads it back via `agentforge.replay.load_pipeline_result` and
threads it into `Agent.run(replay_pipeline=...)` — the agent
sees the recorded findings and skips actual task execution.
Side-effect-bearing tasks (file writes, network calls) don't
double-run on replay.

To exercise the path directly in tests:

```python
from agentforge.replay import load_pipeline_result

recorded = await load_pipeline_result(memory, run_id)
await agent.run(task, replay_pipeline=recorded)
```

## 12. References

- feat-001, feat-008, feat-017
- Archived: `docs/archive/cr/CR-019f-pipeline-descriptor.md`
