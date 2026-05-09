"""Unit tests for the feat-003 capability extensions on `LLMClient`.

Covers:
  - Default-raise behaviour for `call_with_cache`, `call_with_thinking`,
    `stream` on a driver that doesn't declare the capability.
  - Capability declaration via `capabilities()` and the `supports()`
    accessor.
  - Concrete subclasses overriding the optional methods.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production.exceptions import CapabilityNotSupported
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    StopReason,
    StreamChunk,
    TokenUsage,
    ToolSpec,
)


def _resp() -> LLMResponse:
    return LLMResponse(
        content="ok",
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=1, output_tokens=1),
        cost_usd=0.0,
        model="m",
        provider="p",
    )


class _MinimalClient(LLMClient):
    """Driver that only implements the mandatory surface."""

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        return _resp()

    async def close(self) -> None: ...


class _FullCapClient(LLMClient):
    """Driver that overrides every optional method."""

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        return _resp()

    async def close(self) -> None: ...

    def capabilities(self) -> set[str]:
        return {"caching", "thinking", "streaming", "tools"}

    async def call_with_cache(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        cache_breakpoints: list[int],
    ) -> LLMResponse:
        return LLMResponse(
            content=f"cached:{len(cache_breakpoints)}",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
            cost_usd=0.0,
            model="m",
            provider="p",
        )

    async def call_with_thinking(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        thinking_budget_tokens: int,
    ) -> LLMResponse:
        return LLMResponse(
            content=f"thought-with-budget:{thinking_budget_tokens}",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1, thinking_tokens=42),
            cost_usd=0.0,
            model="m",
            provider="p",
        )

    def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        async def _gen() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(kind="text", delta="hello")
            yield StreamChunk(kind="text", delta=" world")
            yield StreamChunk(
                kind="stop",
                stop_reason="end_turn",
                usage=TokenUsage(input_tokens=2, output_tokens=2),
                cost_usd=0.001,
            )

        return _gen()


# ---- Default capabilities ----


def test_minimal_client_declares_no_capabilities() -> None:
    client = _MinimalClient()
    assert client.capabilities() == set()
    assert client.supports("caching") is False
    assert client.supports("anything") is False


def test_full_cap_client_declares_each_capability() -> None:
    client = _FullCapClient()
    caps = client.capabilities()
    for c in ("caching", "thinking", "streaming", "tools"):
        assert c in caps
        assert client.supports(c) is True


# ---- Default-raise on optional methods ----


@pytest.mark.asyncio
async def test_call_with_cache_default_raises_capability_not_supported() -> None:
    client = _MinimalClient()
    with pytest.raises(CapabilityNotSupported, match="caching"):
        await client.call_with_cache("sys", [], cache_breakpoints=[])


@pytest.mark.asyncio
async def test_call_with_thinking_default_raises_capability_not_supported() -> None:
    client = _MinimalClient()
    with pytest.raises(CapabilityNotSupported, match="thinking"):
        await client.call_with_thinking("sys", [], thinking_budget_tokens=100)


@pytest.mark.asyncio
async def test_stream_default_raises_capability_not_supported() -> None:
    client = _MinimalClient()
    with pytest.raises(CapabilityNotSupported, match="streaming"):
        # `stream()` is a sync method that returns an iterator — the
        # raise happens synchronously at the call site.
        client.stream("sys", [])


# ---- Override behaviour ----


@pytest.mark.asyncio
async def test_full_cap_call_with_cache_returns_provider_response() -> None:
    client = _FullCapClient()
    resp = await client.call_with_cache("sys", [], cache_breakpoints=[1, 3])
    assert resp.content == "cached:2"


@pytest.mark.asyncio
async def test_full_cap_call_with_thinking_carries_thinking_tokens() -> None:
    client = _FullCapClient()
    resp = await client.call_with_thinking("sys", [], thinking_budget_tokens=500)
    assert resp.content == "thought-with-budget:500"
    assert resp.usage.thinking_tokens == 42


@pytest.mark.asyncio
async def test_full_cap_stream_yields_text_then_stop_chunk() -> None:
    client = _FullCapClient()
    chunks: list[StreamChunk] = [c async for c in client.stream("sys", [])]
    assert len(chunks) == 3
    assert chunks[0].kind == "text"
    assert chunks[0].delta == "hello"
    assert chunks[-1].kind == "stop"
    assert chunks[-1].stop_reason == "end_turn"
    assert chunks[-1].cost_usd == 0.001


# ---- Optional kwargs surface ----


@pytest.mark.asyncio
async def test_call_with_cache_accepts_empty_breakpoints() -> None:
    """Empty breakpoints is a valid request — equivalent to plain call."""
    client = _FullCapClient()
    resp = await client.call_with_cache("sys", [], cache_breakpoints=[])
    assert resp.content == "cached:0"


# ---- Other capability vocabulary ----


def test_supports_unknown_capability_returns_false() -> None:
    client = _FullCapClient()
    assert client.supports("not-a-real-capability") is False


# ---- StopReason annotation on the contract ----


def test_stream_chunk_kind_includes_thinking() -> None:
    """`thinking` is a valid stream-chunk kind for extended-thinking
    drivers that surface intermediate thoughts."""
    chunk = StreamChunk(kind="thinking", delta="reasoning step")
    assert chunk.kind == "thinking"
    assert chunk.delta == "reasoning step"


def test_stream_chunk_stop_reason_typed() -> None:
    """The terminal stop chunk's `stop_reason` is typed against the
    provider-normalised enum."""
    sr: StopReason = "tool_use"
    chunk = StreamChunk(kind="stop", stop_reason=sr)
    assert chunk.stop_reason == "tool_use"
