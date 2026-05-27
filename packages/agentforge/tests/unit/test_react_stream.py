"""Unit tests for `ReActLoop.stream()` (feat-002 v0.3 polish).

Exercises the per-iteration streaming override:

- LLM emits one tool_call → strategy emits think/act/observe step
  events, plus another think on the next iteration when the LLM
  terminates → terminal `done` event from the strategy.
- `Agent.stream(task)` routes through the strategy's `stream()` and
  swallows its terminal done, emitting the canonical RunResult done.
"""

from __future__ import annotations

import pytest
from agentforge import Agent
from agentforge._testing import FakeLLMClient
from agentforge.strategies.react import ReActLoop
from agentforge_core.contracts.tool import Tool
from agentforge_core.values.messages import (
    LLMResponse,
    TokenUsage,
    ToolCall,
)
from pydantic import BaseModel


class _SearchArgs(BaseModel):
    query: str


class _FakeSearchTool(Tool):
    name = "search"
    description = "echoes the query back"
    input_schema = _SearchArgs

    async def run(self, query: str) -> str:
        return f"results for {query!r}"


def _llm_response(
    *,
    content: str,
    stop_reason: str = "end_turn",
    tool_calls: tuple[ToolCall, ...] = (),
    cost: float = 0.0,
) -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        tool_calls=tool_calls,
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        cost_usd=cost,
        model="fake",
        provider="fake",
    )


@pytest.mark.asyncio
async def test_stream_emits_per_step_then_canonical_done() -> None:
    """Two-iteration ReAct: think → act → observe (iter 0) → think (iter 1, terminates).

    Expected stream from Agent.stream(task): five `step` events plus
    the canonical `done` event emitted by Agent.stream itself.
    """
    fake = FakeLLMClient(
        responses=[
            _llm_response(
                content="I'll search.",
                stop_reason="tool_use",
                tool_calls=(ToolCall(id="t-1", name="search", arguments={"query": "x"}),),
            ),
            _llm_response(content="found it", stop_reason="end_turn"),
        ],
    )
    agent = Agent(model=fake, tools=[_FakeSearchTool()], strategy=ReActLoop())

    events = [event async for event in agent.stream("find x")]
    kinds = [e.kind for e in events]

    # 3 steps on iter-0 (think + act + observe) + 1 step on iter-1 (think) + done.
    assert kinds == ["step", "step", "step", "step", "done"]

    # Every step event carries iteration + kind metadata.
    step_events = [e for e in events if e.kind == "step"]
    iterations = [e.metadata["iteration"] for e in step_events]
    step_kinds = [e.metadata["kind"] for e in step_events]
    assert iterations == [0, 0, 0, 1]
    assert step_kinds == ["think", "act", "observe", "think"]

    # The final done is the agent-canonical one (carries the full RunResult shape).
    done = events[-1]
    assert isinstance(done.content, dict)
    assert "run_id" in done.content
    assert "output" in done.content
    assert "finish_reason" in done.content


@pytest.mark.asyncio
async def test_stream_assistant_turn_round_trips_tool_calls() -> None:
    """bug-009 (stream path): the assistant Message re-fed on iteration 2
    must carry the previous iteration's tool_calls so provider clients
    can emit matching tool-use blocks."""
    tc = ToolCall(id="t-1", name="search", arguments={"query": "x"})
    fake = FakeLLMClient(
        responses=[
            _llm_response(content="I'll search.", stop_reason="tool_use", tool_calls=(tc,)),
            _llm_response(content="found it", stop_reason="end_turn"),
        ],
    )
    agent = Agent(model=fake, tools=[_FakeSearchTool()], strategy=ReActLoop())

    async for _ in agent.stream("find x"):
        pass

    _, iter2_messages, _ = fake.captured[1]
    assistant_turns = [m for m in iter2_messages if m.role == "assistant"]
    assert len(assistant_turns) == 1
    assert assistant_turns[0].tool_calls == (tc,)


@pytest.mark.asyncio
async def test_strategy_stream_yields_strategy_level_done_when_driven_directly() -> None:
    """When a caller drives `strategy.stream(state)` directly (bypassing
    Agent.stream), the strategy's own `done` event surfaces — it carries
    just `run_id` + `cost_usd`, not the full RunResult."""
    from agentforge._testing import FakeTool  # noqa: PLC0415
    from agentforge.runtime import RUNTIME_KEY, RuntimeContext  # noqa: PLC0415
    from agentforge_core.production.budget import BudgetPolicy  # noqa: PLC0415
    from agentforge_core.values.state import AgentState  # noqa: PLC0415

    fake = FakeLLMClient(responses=[_llm_response(content="done")])
    state = AgentState(
        run_id="r-1",
        task="t",
        metadata={
            RUNTIME_KEY: RuntimeContext(
                llm=fake,
                tools=(FakeTool(),),
                memory=None,  # type: ignore[arg-type]
                budget=BudgetPolicy(usd=1.0),
            ),
        },
    )
    strategy = ReActLoop()

    events = [event async for event in strategy.stream(state)]

    assert events[-1].kind == "done"
    assert isinstance(events[-1].content, dict)
    # Strategy-level done is minimal.
    assert set(events[-1].content.keys()) == {"run_id", "cost_usd"}
