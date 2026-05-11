"""Tests for `agentforge.testing.MockLLMClient` (feat-016 chunk 1)."""

from __future__ import annotations

import pytest
from agentforge.testing import MockLLMClient
from agentforge_core.production.exceptions import ModuleError


@pytest.mark.asyncio
async def test_from_script_returns_responses_in_order() -> None:
    mock = MockLLMClient.from_script(
        [
            {"text": "thinking", "tool_calls": [{"name": "search", "args": {"q": "x"}}]},
            {"text": "done", "stop_reason": "end_turn"},
        ]
    )
    first = await mock.call(system="", messages=[])
    assert first.content == "thinking"
    assert first.stop_reason == "tool_use"
    assert first.tool_calls[0].name == "search"

    second = await mock.call(system="", messages=[])
    assert second.content == "done"
    assert second.stop_reason == "end_turn"
    assert second.tool_calls == ()


@pytest.mark.asyncio
async def test_deterministic_factory() -> None:
    mock = MockLLMClient.deterministic("ok")
    out = await mock.call(system="", messages=[])
    assert out.content == "ok"
    assert out.stop_reason == "end_turn"
    assert out.tool_calls == ()


@pytest.mark.asyncio
async def test_call_count_and_tool_calls_observed_tracking() -> None:
    mock = MockLLMClient.from_script(
        [
            {"tool_calls": [{"name": "a", "args": {"x": 1}}]},
            {"tool_calls": [{"name": "b", "args": {"y": 2}}]},
            {"text": "done"},
        ]
    )
    assert mock.call_count == 0
    await mock.call(system="", messages=[])
    await mock.call(system="", messages=[])
    await mock.call(system="", messages=[])
    assert mock.call_count == 3
    assert mock.tool_calls_observed == [("a", {"x": 1}), ("b", {"y": 2})]


@pytest.mark.asyncio
async def test_exhausted_raises_module_error() -> None:
    mock = MockLLMClient.from_script([{"text": "only-one"}])
    await mock.call(system="", messages=[])
    with pytest.raises(ModuleError, match="exhausted"):
        await mock.call(system="", messages=[])


@pytest.mark.asyncio
async def test_tool_call_id_synthesized_when_missing() -> None:
    mock = MockLLMClient.from_script([{"tool_calls": [{"name": "echo", "args": {"text": "hi"}}]}])
    r = await mock.call(system="", messages=[])
    assert r.tool_calls[0].id.startswith("mock-")


def test_re_exports_fake_helpers() -> None:
    from agentforge.testing import FakeLLMClient, FakeTool, echo_response  # noqa: PLC0415

    assert callable(FakeLLMClient)
    assert callable(FakeTool.fake)
    assert callable(echo_response)
