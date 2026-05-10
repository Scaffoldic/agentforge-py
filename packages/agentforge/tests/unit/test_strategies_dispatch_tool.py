"""Unit tests for `_StrategyBase._dispatch_tool` (feat-004 chunk 4).

The helper centralises validation + timeout + exception-to-observation
conversion so all shipped strategies share one tool-call boundary.
"""

from __future__ import annotations

import asyncio

import pytest
from agentforge import tool
from agentforge.strategies._base import StrategyBase
from agentforge_core.values.state import AgentState


class _Probe(StrategyBase):
    """Tiny concrete StrategyBase so we can call protected helpers."""

    async def run(self, state: AgentState) -> AgentState:
        return state


@pytest.fixture
def probe() -> _Probe:
    return _Probe()


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@tool
def explodes(x: int) -> int:
    """Always raises a RuntimeError to exercise exception capture."""
    msg = "boom"
    raise RuntimeError(msg)


@tool
async def slow(x: int) -> int:
    """Sleeps long enough to trip the dispatch timeout."""
    await asyncio.sleep(5)
    return x


# ---- Happy path ----


@pytest.mark.asyncio
async def test_dispatch_runs_validated_tool(probe: _Probe) -> None:
    obs = await probe._dispatch_tool(add, "add", {"a": 2, "b": 3})
    assert obs == "5"


# ---- Tool not registered ----


@pytest.mark.asyncio
async def test_dispatch_returns_observation_when_tool_missing(probe: _Probe) -> None:
    obs = await probe._dispatch_tool(None, "ghost", {})
    assert obs.startswith("Error:")
    assert "not registered" in obs


# ---- Validation failure ----


@pytest.mark.asyncio
async def test_dispatch_returns_observation_on_validation_error(
    probe: _Probe,
) -> None:
    """Wrong type for a parameter → ValidationError → Error observation
    with details (not a stack trace). The LLM sees the validation
    error message and can self-correct on the next iteration."""
    obs = await probe._dispatch_tool(add, "add", {"a": "not an int", "b": 3})
    assert obs.startswith("Error: invalid arguments")


@pytest.mark.asyncio
async def test_dispatch_returns_observation_on_missing_required_arg(
    probe: _Probe,
) -> None:
    obs = await probe._dispatch_tool(add, "add", {"a": 1})
    assert obs.startswith("Error: invalid arguments")


# ---- Tool exception → observation ----


@pytest.mark.asyncio
async def test_dispatch_converts_tool_exception_to_observation(
    probe: _Probe,
) -> None:
    obs = await probe._dispatch_tool(explodes, "explodes", {"x": 1})
    assert obs.startswith("Error: RuntimeError")
    assert "boom" in obs


# ---- Timeout ----


@pytest.mark.asyncio
async def test_dispatch_honours_timeout(probe: _Probe) -> None:
    obs = await probe._dispatch_tool(slow, "slow", {"x": 1}, timeout_s=0.1)
    assert obs.startswith("Error:")
    assert "timeout_s" in obs


@pytest.mark.asyncio
async def test_dispatch_no_timeout_when_none(probe: _Probe) -> None:
    """Passing `timeout_s=None` disables the wait_for wrapper —
    long-running tools are allowed to complete."""
    obs = await probe._dispatch_tool(add, "add", {"a": 1, "b": 2}, timeout_s=None)
    assert obs == "3"


# ---- Return-type coercion ----


@pytest.mark.asyncio
async def test_dispatch_stringifies_non_string_return(probe: _Probe) -> None:
    """Strategies forward observations as `tool` messages; non-string
    returns are coerced to str so the message body always works."""

    @tool
    def returns_dict(k: str) -> dict:
        """Return a dict."""
        return {"k": k, "v": 42}

    obs = await probe._dispatch_tool(returns_dict, "returns_dict", {"k": "hi"})
    assert "v" in obs
    assert "42" in obs
