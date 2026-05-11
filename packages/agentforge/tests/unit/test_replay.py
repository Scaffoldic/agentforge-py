"""Tests for feat-017 replay primitives."""

from __future__ import annotations

import pytest
from agentforge import InMemoryStore
from agentforge.recording import STEP_CATEGORY, RecordRunHook
from agentforge.replay import ReplayExhausted, ReplayLLMClient, replay_tools
from agentforge_core.contracts.tool import Tool
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.claim import Claim
from agentforge_core.values.messages import Message, ToolCall
from agentforge_core.values.state import Step
from pydantic import BaseModel


class _EchoIn(BaseModel):
    text: str


class _EchoTool(Tool):
    name = "echo"
    description = "echo the input back"
    input_schema = _EchoIn

    async def run(self, *, text: str) -> str:
        return f"real: {text}"


async def _record_run(memory: InMemoryStore) -> str:
    hook = RecordRunHook(memory=memory, project="p", agent_name="bot")
    run_id = "01HX-replay-test"
    steps = [
        Step(iteration=0, kind="think", content="reasoning A", tokens_in=10, tokens_out=5),
        Step(
            iteration=0,
            kind="act",
            content={"call": "echo"},
            tool_call=ToolCall(id="t1", name="echo", arguments={"text": "hi"}),
        ),
        Step(iteration=0, kind="observe", content="recorded: hi"),
        Step(iteration=1, kind="think", content="final answer"),
    ]
    # Call put with explicit run_id (RecordRunHook needs an active
    # ContextVar; tests bypass by writing claims directly).
    for step in steps:
        await memory.put(
            Claim(
                run_id=run_id,
                project="p",
                agent="bot",
                category=STEP_CATEGORY,
                payload={
                    "iteration": step.iteration,
                    "kind": step.kind,
                    "content": step.content,
                    "tool_call": step.tool_call.model_dump(mode="json") if step.tool_call else None,
                    "tokens_in": step.tokens_in,
                    "tokens_out": step.tokens_out,
                    "cost_usd": step.cost_usd,
                    "duration_ms": step.duration_ms,
                    "timestamp": step.timestamp.isoformat(),
                    "metadata": dict(step.metadata),
                },
            )
        )
    del hook  # used only for type proximity
    return run_id


@pytest.mark.asyncio
async def test_replay_llm_client_returns_recorded_responses_in_order() -> None:
    memory = InMemoryStore()
    run_id = await _record_run(memory)
    client = await ReplayLLMClient.from_recording(memory, run_id)
    first = await client.call(system="", messages=[Message(role="user", content="x")])
    assert first.content == "reasoning A"
    assert len(first.tool_calls) == 1
    assert first.tool_calls[0].name == "echo"
    assert first.stop_reason == "tool_use"

    second = await client.call(system="", messages=[])
    assert second.content == "final answer"
    assert second.tool_calls == ()
    assert second.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_replay_llm_client_raises_when_exhausted() -> None:
    memory = InMemoryStore()
    run_id = await _record_run(memory)
    client = await ReplayLLMClient.from_recording(memory, run_id)
    await client.call(system="", messages=[])
    await client.call(system="", messages=[])
    with pytest.raises(ReplayExhausted, match="exhausted"):
        await client.call(system="", messages=[])


@pytest.mark.asyncio
async def test_replay_llm_client_missing_recording_errors() -> None:
    memory = InMemoryStore()
    with pytest.raises(ModuleError, match="No recorded steps"):
        await ReplayLLMClient.from_recording(memory, "no-such-run")


@pytest.mark.asyncio
async def test_replay_tools_returns_recorded_observations() -> None:
    memory = InMemoryStore()
    run_id = await _record_run(memory)
    [replayed] = await replay_tools(memory, run_id, [_EchoTool()])
    assert replayed.name == "echo"
    out = await replayed.run(text="anything")
    assert out == "recorded: hi"


@pytest.mark.asyncio
async def test_replay_tool_exhausted_raises() -> None:
    memory = InMemoryStore()
    run_id = await _record_run(memory)
    [replayed] = await replay_tools(memory, run_id, [_EchoTool()])
    await replayed.run(text="anything")
    with pytest.raises(ReplayExhausted, match="exhausted"):
        await replayed.run(text="anything")
