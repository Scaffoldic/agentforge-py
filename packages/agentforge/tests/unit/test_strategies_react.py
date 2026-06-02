"""Unit tests for `ReActLoop`."""

from __future__ import annotations

from typing import Any

import pytest
from agentforge import InMemoryStore
from agentforge._testing import FakeLLMClient
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies import ReActLoop
from agentforge.strategies.react import DEFAULT_SYSTEM_PROMPT
from agentforge_core import (
    BudgetExceeded,
    BudgetPolicy,
    GuardrailViolation,
)
from agentforge_core.contracts.tool import Tool
from agentforge_core.resolver import Resolver
from agentforge_core.values.messages import (
    LLMResponse,
    TokenUsage,
    ToolCall,
)
from agentforge_core.values.state import AgentState
from pydantic import BaseModel

# ---- Test fixtures ----


class _PingInput(BaseModel):
    target: str


class _PingTool(Tool):
    name = "ping"
    description = "Ping a target."
    input_schema = _PingInput

    async def run(self, target: str) -> dict[str, Any]:
        return {"target": target, "ok": True}


class _BoomInput(BaseModel):
    pass


class _BoomTool(Tool):
    """Tool that raises — exercises the error-streak path."""

    name = "boom"
    description = "Always raises."
    input_schema = _BoomInput

    async def run(self) -> Any:
        raise RuntimeError("kaboom")


def _resp(
    *,
    content: str = "",
    tool_calls: tuple[ToolCall, ...] = (),
    stop_reason: str = "end_turn",
    cost: float = 0.001,
    tokens_in: int = 5,
    tokens_out: int = 3,
) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=tool_calls,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        usage=TokenUsage(input_tokens=tokens_in, output_tokens=tokens_out),
        cost_usd=cost,
        model="fake",
        provider="fake",
    )


def _state_for(
    fake: FakeLLMClient,
    *,
    tools: tuple[Tool, ...] = (),
    budget: BudgetPolicy | None = None,
    system_prompt: str | None = None,
) -> AgentState:
    rt = RuntimeContext(
        llm=fake,
        tools=tools,
        memory=InMemoryStore(),
        budget=budget if budget is not None else BudgetPolicy(usd=1.0, max_iterations=10),
        system_prompt=system_prompt,
    )
    return AgentState(run_id="r1", task="ping example.com", metadata={RUNTIME_KEY: rt})


# ---- Tests ----


@pytest.mark.asyncio
async def test_terminates_immediately_when_no_tool_calls() -> None:
    """LLM returns final answer with no tool calls — loop exits."""
    fake = FakeLLMClient(responses=[_resp(content="The answer is 42.")])
    state = _state_for(fake)

    await ReActLoop().run(state)

    assert fake.call_count == 1
    assert len(state.steps) == 1
    assert state.steps[0].kind == "think"
    assert state.steps[0].content == "The answer is 42."


@pytest.mark.asyncio
async def test_dispatches_tool_call_then_finishes() -> None:
    """One tool call, then LLM returns no tool call → finished."""
    fake = FakeLLMClient(
        responses=[
            _resp(
                content="I'll ping example.com.",
                tool_calls=(ToolCall(id="t1", name="ping", arguments={"target": "example.com"}),),
                stop_reason="tool_use",
            ),
            _resp(content="example.com is up."),
        ]
    )
    state = _state_for(fake, tools=(_PingTool(),))

    await ReActLoop().run(state)

    assert fake.call_count == 2
    kinds = [s.kind for s in state.steps]
    assert kinds == ["think", "act", "observe", "think"]
    # observe step content includes the tool result
    observe = state.steps[2]
    assert "example.com" in str(observe.content)
    assert observe.tool_call is not None
    assert observe.tool_call.id == "t1"


@pytest.mark.asyncio
async def test_assistant_turn_round_trips_tool_calls() -> None:
    """bug-009: the assistant Message re-fed on iteration 2 must carry
    the previous iteration's tool_calls so provider clients can emit
    matching tool-use blocks (Bedrock toolUse, OpenAI tool_calls,
    Anthropic tool_use)."""
    tc = ToolCall(id="t1", name="ping", arguments={"target": "example.com"})
    fake = FakeLLMClient(
        responses=[
            _resp(
                content="I'll ping example.com.",
                tool_calls=(tc,),
                stop_reason="tool_use",
            ),
            _resp(content="example.com is up."),
        ]
    )
    state = _state_for(fake, tools=(_PingTool(),))

    await ReActLoop().run(state)

    # captured[1] is the iteration-2 call: (system, messages, tools).
    _, iter2_messages, _ = fake.captured[1]
    assistant_turns = [m for m in iter2_messages if m.role == "assistant"]
    assert len(assistant_turns) == 1
    assert assistant_turns[0].tool_calls == (tc,)


@pytest.mark.asyncio
async def test_unknown_tool_recorded_as_error_observation() -> None:
    """LLM emits a tool name that isn't in the agent's catalogue —
    recorded as observation; error_streak increments; agent continues."""
    fake = FakeLLMClient(
        responses=[
            _resp(
                content="trying nonexistent",
                tool_calls=(ToolCall(id="t1", name="not_registered", arguments={}),),
                stop_reason="tool_use",
            ),
            _resp(content="ok, giving up."),
        ]
    )
    state = _state_for(fake, tools=())

    await ReActLoop().run(state)

    # The observe step contains the error message
    observe = state.steps[2]
    assert observe.kind == "observe"
    assert "not_registered" in str(observe.content)
    # Error streak incremented
    rt = state.metadata[RUNTIME_KEY]
    assert rt.budget.error_streak >= 1


@pytest.mark.asyncio
async def test_tool_exception_surfaced_as_observation() -> None:
    """Tool raises → observation contains 'Error:'; error_streak increments."""
    fake = FakeLLMClient(
        responses=[
            _resp(
                content="trying boom",
                tool_calls=(ToolCall(id="t1", name="boom", arguments={}),),
                stop_reason="tool_use",
            ),
            _resp(content="recovered."),
        ]
    )
    state = _state_for(fake, tools=(_BoomTool(),))

    await ReActLoop().run(state)

    observe = state.steps[2]
    assert "Error" in str(observe.content)
    assert "kaboom" in str(observe.content)


@pytest.mark.asyncio
async def test_guardrail_iteration_cap_terminates_loop() -> None:
    """Reaches max_iterations; loop bails with GuardrailViolation."""
    # Always emit a tool call so the loop never naturally finishes.
    looper = lambda **_: _resp(  # noqa: E731
        content="loop",
        tool_calls=(ToolCall(id=f"t{id(_)}", name="ping", arguments={"target": "x"}),),
        stop_reason="tool_use",
    )
    fake = FakeLLMClient(responses=[looper] * 20)
    state = _state_for(fake, tools=(_PingTool(),), budget=BudgetPolicy(usd=10.0, max_iterations=2))

    with pytest.raises(GuardrailViolation):
        await ReActLoop().run(state)


@pytest.mark.asyncio
async def test_budget_cap_terminates_loop() -> None:
    """Each LLM call costs more than the cap; second iteration trips it."""
    expensive = _resp(
        content="thinking",
        tool_calls=(ToolCall(id="t1", name="ping", arguments={"target": "x"}),),
        stop_reason="tool_use",
        cost=0.6,
    )
    fake = FakeLLMClient(responses=[expensive, expensive, expensive])
    state = _state_for(fake, tools=(_PingTool(),), budget=BudgetPolicy(usd=1.0, max_iterations=10))

    with pytest.raises(BudgetExceeded):
        await ReActLoop().run(state)


@pytest.mark.asyncio
async def test_max_iterations_override() -> None:
    """Constructor max_iterations overrides BudgetPolicy.max_iterations."""
    looper = lambda **_: _resp(  # noqa: E731
        tool_calls=(ToolCall(id=f"t{id(_)}", name="ping", arguments={"target": "x"}),),
        stop_reason="tool_use",
    )
    fake = FakeLLMClient(responses=[looper] * 20)
    state = _state_for(fake, tools=(_PingTool(),), budget=BudgetPolicy(usd=10.0, max_iterations=10))

    with pytest.raises(GuardrailViolation):
        await ReActLoop(max_iterations=2).run(state)
    rt = state.metadata[RUNTIME_KEY]
    assert rt.budget.max_iterations == 2


@pytest.mark.asyncio
async def test_uses_runtime_system_prompt() -> None:
    fake = FakeLLMClient(responses=[_resp(content="ok")])
    state = _state_for(fake, system_prompt="Custom system prompt.")
    await ReActLoop().run(state)
    captured_system, _, _ = fake.captured[0]
    assert captured_system == "Custom system prompt."


@pytest.mark.asyncio
async def test_default_system_prompt_used_when_runtime_unset() -> None:
    fake = FakeLLMClient(responses=[_resp(content="ok")])
    state = _state_for(fake)
    await ReActLoop().run(state)
    captured_system, _, _ = fake.captured[0]
    assert captured_system == DEFAULT_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_passes_tool_specs_to_llm() -> None:
    fake = FakeLLMClient(responses=[_resp(content="ok")])
    state = _state_for(fake, tools=(_PingTool(),))
    await ReActLoop().run(state)
    _, _, tools = fake.captured[0]
    assert tools is not None
    assert len(tools) == 1
    assert tools[0].name == "ping"


@pytest.mark.asyncio
async def test_no_tools_passes_none_to_llm() -> None:
    fake = FakeLLMClient(responses=[_resp(content="ok")])
    state = _state_for(fake, tools=())
    await ReActLoop().run(state)
    _, _, tools = fake.captured[0]
    assert tools is None


def test_react_registered_under_strategies_react() -> None:
    """The @register_strategy('react') decorator at class-definition
    time registers ReActLoop with the global resolver."""
    cls = Resolver.global_().resolve("strategies", "react")
    assert cls is ReActLoop
