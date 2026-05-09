"""Unit tests for `PlanExecuteLoop`."""

from __future__ import annotations

from typing import Any

import pytest
from agentforge import InMemoryStore
from agentforge._testing import FakeLLMClient
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies import PlanExecuteLoop
from agentforge_core import BudgetPolicy
from agentforge_core.contracts.tool import Tool
from agentforge_core.resolver import Resolver
from agentforge_core.values.messages import LLMResponse, TokenUsage
from agentforge_core.values.state import AgentState
from pydantic import BaseModel

# ---- Fixtures ----


class _AddInput(BaseModel):
    a: int
    b: int


class _AddTool(Tool):
    name = "add"
    description = "Add two integers."
    input_schema = _AddInput

    async def run(self, a: int, b: int) -> dict[str, Any]:
        return {"sum": a + b}


class _BoomInput(BaseModel):
    pass


class _BoomTool(Tool):
    name = "boom"
    description = "Always raises."
    input_schema = _BoomInput

    async def run(self) -> Any:
        raise RuntimeError("kaboom")


def _resp(content: str = "") -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=5, output_tokens=3),
        cost_usd=0.001,
        model="fake",
        provider="fake",
    )


def _state_for(
    fake: FakeLLMClient,
    *,
    tools: tuple[Tool, ...] = (),
    budget: BudgetPolicy | None = None,
) -> AgentState:
    rt = RuntimeContext(
        llm=fake,
        tools=tools,
        memory=InMemoryStore(),
        budget=budget if budget is not None else BudgetPolicy(usd=10.0, max_iterations=20),
    )
    return AgentState(run_id="r1", task="add 2 + 3", metadata={RUNTIME_KEY: rt})


_VALID_PLAN_JSON = (
    '{"steps": ['
    '{"id": "step-1", "description": "add 2+3", '
    '"tool": "add", "arguments": {"a": 2, "b": 3}, "depends_on": []}'
    "]}"
)

_PARALLEL_PLAN_JSON = (
    '{"steps": ['
    '{"id": "a", "description": "add 1+1", "tool": "add", '
    '"arguments": {"a": 1, "b": 1}, "depends_on": []},'
    '{"id": "b", "description": "add 2+2", "tool": "add", '
    '"arguments": {"a": 2, "b": 2}, "depends_on": []}'
    "]}"
)


# ---- Tests ----


def test_constructor_validates_max_parallel_steps() -> None:
    with pytest.raises(ValueError, match="max_parallel_steps"):
        PlanExecuteLoop(max_parallel_steps=0)


def test_constructor_validates_max_replans() -> None:
    with pytest.raises(ValueError, match="max_replans"):
        PlanExecuteLoop(max_replans=-1)


def test_registered_under_strategies_plan_execute() -> None:
    cls = Resolver.global_().resolve("strategies", "plan-execute")
    assert cls is PlanExecuteLoop


@pytest.mark.asyncio
async def test_single_step_plan_executes_and_synthesizes() -> None:
    """One-step plan: plan → execute (1 step) → synthesize."""
    fake = FakeLLMClient(
        responses=[
            _resp(_VALID_PLAN_JSON),
            _resp("Final answer: 5."),
        ]
    )
    state = _state_for(fake, tools=(_AddTool(),))
    await PlanExecuteLoop().run(state)

    assert fake.call_count == 2  # plan call + synthesis call
    kinds = [s.kind for s in state.steps]
    assert "plan" in kinds
    assert "act" in kinds
    assert "observe" in kinds
    assert "synthesize" in kinds


@pytest.mark.asyncio
async def test_parallel_independent_steps_in_one_batch() -> None:
    """Two independent steps run in the same batch."""
    fake = FakeLLMClient(
        responses=[
            _resp(_PARALLEL_PLAN_JSON),
            _resp("Both done."),
        ]
    )
    state = _state_for(fake, tools=(_AddTool(),))
    await PlanExecuteLoop(max_parallel_steps=2).run(state)

    # Two `act` steps + two `observe` steps for the parallel batch.
    acts = [s for s in state.steps if s.kind == "act"]
    observes = [s for s in state.steps if s.kind == "observe"]
    assert len(acts) == 2
    assert len(observes) == 2


@pytest.mark.asyncio
async def test_invalid_plan_triggers_replan() -> None:
    """First plan is malformed JSON; LLM corrects on retry."""
    fake = FakeLLMClient(
        responses=[
            _resp("not valid JSON"),
            _resp(_VALID_PLAN_JSON),
            _resp("Done."),
        ]
    )
    state = _state_for(fake, tools=(_AddTool(),))
    await PlanExecuteLoop(max_replans=1).run(state)

    assert fake.call_count == 3  # malformed + corrected + synthesis


@pytest.mark.asyncio
async def test_invalid_plan_after_max_replans_raises() -> None:
    fake = FakeLLMClient(
        responses=[
            _resp("not valid"),
            _resp("still not valid"),
        ]
    )
    state = _state_for(fake, tools=(_AddTool(),))
    with pytest.raises(Exception, match="invalid"):
        await PlanExecuteLoop(max_replans=1).run(state)


@pytest.mark.asyncio
async def test_step_failure_triggers_replan() -> None:
    """First plan uses a failing tool; replan with a different plan."""
    bad_plan = (
        '{"steps": [{"id": "x", "description": "boom", '
        '"tool": "boom", "arguments": {}, "depends_on": []}]}'
    )
    fake = FakeLLMClient(
        responses=[
            _resp(bad_plan),
            _resp(_VALID_PLAN_JSON),
            _resp("Done."),
        ]
    )
    state = _state_for(fake, tools=(_AddTool(), _BoomTool()))
    await PlanExecuteLoop(replan_on_failure=True, max_replans=1).run(state)

    assert fake.call_count == 3


@pytest.mark.asyncio
async def test_step_failure_without_replan_records_error_and_synthesizes() -> None:
    bad_plan = (
        '{"steps": [{"id": "x", "description": "boom", '
        '"tool": "boom", "arguments": {}, "depends_on": []}]}'
    )
    fake = FakeLLMClient(
        responses=[
            _resp(bad_plan),
            _resp("Failure synthesized."),
        ]
    )
    state = _state_for(fake, tools=(_BoomTool(),))
    await PlanExecuteLoop(replan_on_failure=False).run(state)

    # Strategy continues despite the failure
    assert fake.call_count == 2
    error_observes = [s for s in state.steps if s.kind == "observe" and "Error" in str(s.content)]
    assert len(error_observes) >= 1


@pytest.mark.asyncio
async def test_think_only_step_no_tool() -> None:
    """A step with tool=None makes one LLM call and records its content."""
    plan_json = (
        '{"steps": [{"id": "a", "description": "think about life", '
        '"tool": null, "arguments": {}, "depends_on": []}]}'
    )
    fake = FakeLLMClient(
        responses=[
            _resp(plan_json),
            _resp("the answer is 42"),  # think step
            _resp("Final synthesis."),
        ]
    )
    state = _state_for(fake)
    await PlanExecuteLoop().run(state)

    assert fake.call_count == 3


@pytest.mark.asyncio
async def test_max_parallel_steps_respected() -> None:
    """Three independent steps with max_parallel_steps=1 → still one batch
    by topology, but execution serialises through the semaphore."""
    plan_json = (
        '{"steps": ['
        '{"id": "a", "description": "x", "tool": "add", '
        '"arguments": {"a": 1, "b": 1}, "depends_on": []},'
        '{"id": "b", "description": "y", "tool": "add", '
        '"arguments": {"a": 2, "b": 2}, "depends_on": []},'
        '{"id": "c", "description": "z", "tool": "add", '
        '"arguments": {"a": 3, "b": 3}, "depends_on": []}'
        "]}"
    )
    fake = FakeLLMClient(responses=[_resp(plan_json), _resp("done")])
    state = _state_for(fake, tools=(_AddTool(),))
    await PlanExecuteLoop(max_parallel_steps=1).run(state)

    # All three steps should still execute and observe.
    observes = [s for s in state.steps if s.kind == "observe"]
    assert len(observes) == 3


@pytest.mark.asyncio
async def test_strips_code_fences_from_llm_plan_output() -> None:
    """LLMs sometimes wrap JSON in ```json ... ``` fences. Parser handles."""
    fenced = "```json\n" + _VALID_PLAN_JSON + "\n```"
    fake = FakeLLMClient(responses=[_resp(fenced), _resp("done")])
    state = _state_for(fake, tools=(_AddTool(),))
    await PlanExecuteLoop().run(state)
    assert fake.call_count == 2
