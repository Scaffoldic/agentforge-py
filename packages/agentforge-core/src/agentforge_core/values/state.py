"""`AgentState`, `Step`, `RunResult` — the trace shape of an agent run.

Per ADR-0008, `state.steps` is uniform across reasoning strategies so
debugging skills transfer between agents that use different loop
shapes (ReAct, Plan-Execute, ToT, Multi-Agent).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agentforge_core.contracts.evaluator import EvalResult
from agentforge_core.values.messages import ToolCall

StepKind = Literal[
    "think",
    "act",
    "observe",
    "plan",
    "synthesize",
    "branch",
    "delegate",
    "system",
]
"""Closed enum of step kinds. Every reasoning strategy emits steps from
this set; new kinds require a feature doc + minor version bump."""

FinishReason = Literal[
    "completed",
    "iteration_cap",
    "budget_exceeded",
    "guardrail",
    "pipeline",
    "error",
    "cancelled",
]
"""How a run terminated. Mirrors the runtime's branching of
`BudgetExceeded` / `GuardrailViolation` / `PipelineFailure` / clean
completion."""


class Step(BaseModel):
    """One unit of progress in `AgentState.steps`."""

    model_config = ConfigDict(frozen=True, strict=True)

    iteration: int = Field(ge=0)
    kind: StepKind
    content: str | dict[str, Any]
    tool_call: ToolCall | None = None
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    duration_ms: int = Field(default=0, ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """Mutable per-run state passed through the reasoning loop.

    Strategies append to `steps`; tools and pipeline tasks may append
    to `findings`. The runtime owns the lifecycle.

    The per-run execution context (`RuntimeContext` — LLM client,
    tools, memory, budget, system prompt) is stored on
    `state.metadata` under the key `"__agentforge_runtime__"`,
    populated by `Agent.run()` before calling the strategy.
    Strategies access it via the `get_runtime(state)` helper in
    `agentforge.strategies._base`. Storing it on metadata keeps
    `agentforge-core` free of dependencies on runtime modules.
    """

    model_config = ConfigDict(strict=True, validate_assignment=True)

    run_id: str
    task: str
    steps: list[Step] = Field(default_factory=list)
    findings: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    """Final, immutable output of `Agent.run()`.

    Carries the agent's answer plus full trace, cost accounting, and the
    run's `run_id` for cross-system correlation (ADR-0010).
    """

    model_config = ConfigDict(frozen=True, strict=True)

    output: str | dict[str, Any]
    findings: tuple[Any, ...] = ()
    steps: tuple[Step, ...] = ()
    cost_usd: float = Field(ge=0.0)
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    run_id: str
    duration_ms: int = Field(ge=0)
    finish_reason: FinishReason = "completed"
    metadata: dict[str, Any] = Field(default_factory=dict)
    guardrail_events: tuple[dict[str, Any], ...] = ()
    """feat-018: one entry per guardrail decision (input / output /
    tool-gate). Each event carries `validator`, `passed`, `violations`,
    `action`, `stage` ("input" / "output" / "tool"), and a hash of the
    content (full content is never persisted here)."""

    eval_scores: tuple[EvalResult, ...] = ()
    """Per-evaluator `EvalResult` from the post-run evaluator pass.

    Ordered by the order evaluators were configured on the Agent.
    Empty when no evaluators ran (no `evaluators=` passed) or when
    every evaluator was budget-skipped. See feat-006 §4.3 for the
    cost-gating rule.
    """
