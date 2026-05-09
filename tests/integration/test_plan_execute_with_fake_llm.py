"""Integration test — Agent + PlanExecuteLoop end-to-end."""

from __future__ import annotations

from typing import Any

import pytest
from agentforge import Agent, PlanExecuteLoop
from agentforge._testing import FakeLLMClient
from agentforge_core.contracts.tool import Tool
from agentforge_core.values.messages import LLMResponse, TokenUsage
from pydantic import BaseModel


class _MultInput(BaseModel):
    a: int
    b: int


class _MultTool(Tool):
    name = "multiply"
    description = "Multiply two integers."
    input_schema = _MultInput

    async def run(self, a: int, b: int) -> dict[str, Any]:
        return {"product": a * b}


def _r(content: str = "") -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=8, output_tokens=4),
        cost_usd=0.001,
        model="fake",
        provider="fake",
    )


_PARALLEL_PLAN = (
    '{"steps": ['
    '{"id": "p1", "description": "2*3", "tool": "multiply", '
    '"arguments": {"a": 2, "b": 3}, "depends_on": []},'
    '{"id": "p2", "description": "4*5", "tool": "multiply", '
    '"arguments": {"a": 4, "b": 5}, "depends_on": []},'
    '{"id": "p3", "description": "sum", "tool": null, '
    '"arguments": {}, "depends_on": ["p1", "p2"]}'
    "]}"
)


@pytest.mark.asyncio
async def test_string_strategy_plan_execute_runs_full_pipeline() -> None:
    fake = FakeLLMClient(
        responses=[
            _r(_PARALLEL_PLAN),
            _r("p3 thought: sum is 6 + 20 = 26"),
            _r("Final answer: 26."),
        ]
    )
    async with Agent(
        model=fake,
        tools=[_MultTool()],
        strategy="plan-execute",
        budget_usd=2.0,
        install_log_filter=False,
    ) as agent:
        result = await agent.run("Compute 2*3 + 4*5")

    assert result.output == "Final answer: 26."
    assert result.finish_reason == "completed"
    assert fake.call_count == 3  # plan + p3 think + synthesis
    # Expect plan + 2 acts + 2 observes (parallel batch) + 1 observe (think) + synthesize
    kinds = {s.kind for s in result.steps}
    assert "plan" in kinds
    assert "act" in kinds
    assert "observe" in kinds
    assert "synthesize" in kinds


@pytest.mark.asyncio
async def test_typed_plan_execute_instance() -> None:
    fake = FakeLLMClient(
        responses=[
            _r(
                '{"steps": [{"id": "x", "description": "do", '
                '"tool": null, "arguments": {}, "depends_on": []}]}'
            ),
            _r("did it"),
            _r("ok"),
        ]
    )
    async with Agent(
        model=fake,
        strategy=PlanExecuteLoop(max_parallel_steps=2, max_replans=0),
        install_log_filter=False,
    ) as agent:
        result = await agent.run("test")

    assert result.output == "ok"
