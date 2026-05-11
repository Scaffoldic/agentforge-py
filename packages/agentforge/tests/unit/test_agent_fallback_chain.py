"""Verify `Agent(model=FallbackChain([...]))` works end-to-end
(feat-007 chunk 2)."""

from __future__ import annotations

from typing import Any

import agentforge as af
import pytest
from agentforge import Agent, FallbackChain, ReActLoop
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production import RateLimitError
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolSpec,
)


class _ScriptedClient(LLMClient):
    """Minimal LLMClient that yields a script of (response | exception)."""

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.calls = 0

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        self.calls += 1
        if not self._script:
            raise RateLimitError("script exhausted")
        item = self._script.pop(0)
        if isinstance(item, type) and issubclass(item, BaseException):
            raise item("scripted")
        return item  # type: ignore[no-any-return]

    async def close(self) -> None:
        pass


def _ok_response(text: str) -> LLMResponse:
    return LLMResponse(
        content=text,
        tool_calls=(),
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=1, output_tokens=1),
        cost_usd=0.0,
        model="fake",
        provider="fake",
    )


# ---- Agent accepts a FallbackChain transparently ----


def test_agent_constructor_accepts_chain() -> None:
    """`Agent(model=FallbackChain([...]))` sets `_llm` to the chain
    instance directly — no string parsing, no resolver lookup."""
    chain = FallbackChain([_ScriptedClient([])])
    agent = Agent(model=chain, strategy=ReActLoop())
    assert agent._llm is chain  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_agent_run_uses_first_provider_when_healthy() -> None:
    a = _ScriptedClient([_ok_response("from-a")])
    b = _ScriptedClient([_ok_response("from-b")])
    chain = FallbackChain([a, b])
    agent = Agent(model=chain, strategy=ReActLoop(max_iterations=2))
    result = await agent.run("hi")
    assert "from-a" in result.output
    assert b.calls == 0
    await agent.close()


@pytest.mark.asyncio
async def test_agent_run_falls_back_on_rate_limit() -> None:
    a = _ScriptedClient([RateLimitError])
    b = _ScriptedClient([_ok_response("from-b")])
    chain = FallbackChain([a, b])
    agent = Agent(model=chain, strategy=ReActLoop(max_iterations=2))
    result = await agent.run("hi")
    assert "from-b" in result.output
    assert chain.last_used_provider == 1
    await agent.close()


# ---- Top-level re-export ----


def test_fallback_chain_importable_from_agentforge() -> None:
    """`from agentforge import FallbackChain` is the documented
    public surface for agent authors. The top-level imports of
    this test file already establish that; this assertion confirms
    the bound name is the same class as the canonical core export."""
    assert af.FallbackChain is FallbackChain
