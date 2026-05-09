"""Integration test — `Agent + ReActLoop + FakeLLM + real tools + InMemoryStore`.

End-to-end exercise of feat-002 chunk 2 against the framework wiring
shipped in feat-001 chunk 1. Verifies that string-resolved
`strategy="react"` works end to end (resolver lookup → instance →
runtime injection → loop → result).
"""

from __future__ import annotations

from typing import Any

import pytest
from agentforge import Agent, ReActLoop
from agentforge._testing import FakeLLMClient
from agentforge_core.contracts.tool import Tool
from agentforge_core.values.messages import LLMResponse, TokenUsage, ToolCall
from pydantic import BaseModel


class _AddInput(BaseModel):
    a: int
    b: int


class _AddTool(Tool):
    name = "add"
    description = "Add two integers."
    input_schema = _AddInput

    async def run(self, a: int, b: int) -> dict[str, Any]:
        return {"sum": a + b}


def _r(
    *,
    content: str = "",
    tool_calls: tuple[ToolCall, ...] = (),
    stop_reason: str = "end_turn",
) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=tool_calls,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        cost_usd=0.001,
        model="fake",
        provider="fake",
    )


@pytest.mark.asyncio
async def test_string_strategy_react_runs_full_loop() -> None:
    """Agent(strategy='react') wires up the registered ReActLoop and
    runs a full think → act → observe → think (final) cycle."""
    fake = FakeLLMClient(
        responses=[
            _r(
                content="I will add 17 and 25.",
                tool_calls=(ToolCall(id="t1", name="add", arguments={"a": 17, "b": 25}),),
                stop_reason="tool_use",
            ),
            _r(content="The answer is 42."),
        ]
    )

    async with Agent(
        model=fake,
        tools=[_AddTool()],
        strategy="react",
        budget_usd=1.0,
        install_log_filter=False,
    ) as agent:
        result = await agent.run("What is 17 + 25?")

    assert result.output == "The answer is 42."
    assert result.cost_usd == pytest.approx(0.002)  # 2 LLM calls at 0.001 each
    assert result.tokens_in == 20
    assert result.tokens_out == 10
    assert result.finish_reason == "completed"
    # Step trace: think (call 1) → act → observe → think (call 2)
    kinds = [s.kind for s in result.steps]
    assert kinds == ["think", "act", "observe", "think"]


@pytest.mark.asyncio
async def test_typed_react_instance_runs() -> None:
    """Passing a typed ReActLoop instance also works (escape hatch)."""
    fake = FakeLLMClient(responses=[_r(content="done.")])
    async with Agent(
        model=fake,
        strategy=ReActLoop(max_iterations=10),
        install_log_filter=False,
    ) as agent:
        result = await agent.run("hi")
    assert result.output == "done."


@pytest.mark.asyncio
async def test_repeated_runs_get_fresh_budget() -> None:
    """Bug-carry from feat-001: each Agent.run() must use a fresh
    BudgetPolicy so spent_usd doesn't leak across runs."""
    fake = FakeLLMClient(responses=[_r(content="r1"), _r(content="r2")])
    async with Agent(
        model=fake, strategy="react", budget_usd=1.0, install_log_filter=False
    ) as agent:
        r1 = await agent.run("first")
        r2 = await agent.run("second")
    # Each run cost the same (~0.001). r2 should not see r1's spend.
    assert r1.cost_usd == pytest.approx(0.001)
    assert r2.cost_usd == pytest.approx(0.001)
