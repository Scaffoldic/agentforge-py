"""Unit tests for `FallbackChain` (feat-007 chunk 1)."""

from __future__ import annotations

from typing import Any

import pytest
from agentforge_core import FallbackChain
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production import (
    AuthenticationError,
    CapabilityNotSupported,
    ProviderError,
    RateLimitError,
)
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolSpec,
)

# ----------------------------------------------------------------------
# Test doubles
# ----------------------------------------------------------------------


def _response(text: str = "ok") -> LLMResponse:
    return LLMResponse(
        content=text,
        tool_calls=(),
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        cost_usd=0.0,
        model="fake",
        provider="fake",
    )


class _ScriptedClient(LLMClient):
    """LLMClient that yields a script of (response | exception) per call.

    Each `call` pops the next item: if a callable, it's invoked; if
    an exception class, it's raised; otherwise returned as-is.
    """

    def __init__(
        self,
        script: list[Any],
        *,
        capabilities_set: set[str] | None = None,
    ) -> None:
        self._script = list(script)
        self._caps = capabilities_set or set()
        self.calls: list[tuple[Any, ...]] = []
        self.closed = False

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        self.calls.append((system, messages, tools))
        if not self._script:
            raise ProviderError("script exhausted")
        item = self._script.pop(0)
        if isinstance(item, type) and issubclass(item, BaseException):
            raise item("scripted")
        if callable(item):
            return item()  # type: ignore[no-any-return]
        return item  # type: ignore[no-any-return]

    async def close(self) -> None:
        self.closed = True

    def capabilities(self) -> set[str]:
        return set(self._caps)


# ----------------------------------------------------------------------
# Constructor
# ----------------------------------------------------------------------


def test_constructor_rejects_empty_providers() -> None:
    with pytest.raises(ValueError, match="at least one provider"):
        FallbackChain([])


def test_constructor_rejects_zero_attempts_per_provider() -> None:
    client = _ScriptedClient([])
    with pytest.raises(ValueError, match="attempts_per_provider"):
        FallbackChain([client], attempts_per_provider=0)


def test_constructor_rejects_non_str_non_client() -> None:
    with pytest.raises(TypeError, match="must be str or LLMClient"):
        FallbackChain([42])  # type: ignore[list-item]


def test_constructor_rejects_unknown_provider_string() -> None:
    with pytest.raises(ValueError, match="no LLM provider registered"):
        FallbackChain(["never-registered:model-x"])


def test_constructor_accepts_typed_clients() -> None:
    a = _ScriptedClient([])
    b = _ScriptedClient([])
    chain = FallbackChain([a, b])
    assert chain.providers == (a, b)


# ----------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_provider_success_short_circuits() -> None:
    a = _ScriptedClient([_response("from-a")])
    b = _ScriptedClient([_response("from-b")])
    chain = FallbackChain([a, b])
    result = await chain.call(system="s", messages=[])
    assert result.content == "from-a"
    assert b.calls == []  # b never invoked
    assert chain.last_used_provider == 0


# ----------------------------------------------------------------------
# Fallback on retry_on
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_falls_back_on_rate_limit_error() -> None:
    a = _ScriptedClient([RateLimitError])
    b = _ScriptedClient([_response("from-b")])
    chain = FallbackChain([a, b])
    result = await chain.call(system="s", messages=[])
    assert result.content == "from-b"
    assert chain.last_used_provider == 1


@pytest.mark.asyncio
async def test_falls_back_on_provider_error() -> None:
    a = _ScriptedClient([ProviderError])
    b = _ScriptedClient([_response("ok")])
    chain = FallbackChain([a, b])
    await chain.call(system="s", messages=[])
    assert chain.last_used_provider == 1


@pytest.mark.asyncio
async def test_default_retry_on_includes_authentication_error() -> None:
    """The spec's default `retry_on=(RateLimitError, ProviderError)`
    catches every `ProviderError` subclass via inheritance — including
    `AuthenticationError`. The intent is "fall back on anything
    provider-related": one provider's auth being misconfigured is a
    legitimate reason to try the next one (which has its own auth).
    Callers who want stricter behaviour can pass a tighter
    `retry_on=(RateLimitError,)` etc."""
    a = _ScriptedClient([AuthenticationError])
    b = _ScriptedClient([_response("from-b")])
    chain = FallbackChain([a, b])
    result = await chain.call(system="s", messages=[])
    assert result.content == "from-b"


@pytest.mark.asyncio
async def test_tight_retry_on_excludes_authentication() -> None:
    """With `retry_on=(RateLimitError,)`, auth errors bubble
    immediately because they're outside the explicit allowlist."""
    a = _ScriptedClient([AuthenticationError])
    b = _ScriptedClient([_response("from-b")])
    chain = FallbackChain([a, b], retry_on=(RateLimitError,))
    with pytest.raises(AuthenticationError):
        await chain.call(system="s", messages=[])
    assert b.calls == []


@pytest.mark.asyncio
async def test_custom_retry_on_with_unrelated_exception() -> None:
    """The user can opt into falling back on any exception type."""

    class _CustomError(Exception):
        pass

    a = _ScriptedClient([_CustomError])
    b = _ScriptedClient([_response("recovered")])
    chain = FallbackChain([a, b], retry_on=(_CustomError,))
    result = await chain.call(system="s", messages=[])
    assert result.content == "recovered"


# ----------------------------------------------------------------------
# attempts_per_provider
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attempts_per_provider_retries_before_falling_through() -> None:
    a = _ScriptedClient([RateLimitError, RateLimitError, _response("third try")])
    chain = FallbackChain([a], attempts_per_provider=3)
    result = await chain.call(system="s", messages=[])
    assert result.content == "third try"
    assert len(a.calls) == 3


@pytest.mark.asyncio
async def test_attempts_per_provider_then_fallback() -> None:
    """Each provider gets `attempts_per_provider` chances; on
    exhaustion, the chain moves to the next provider."""
    a = _ScriptedClient([RateLimitError, RateLimitError])
    b = _ScriptedClient([_response("from-b")])
    chain = FallbackChain([a, b], attempts_per_provider=2)
    result = await chain.call(system="s", messages=[])
    assert result.content == "from-b"
    assert len(a.calls) == 2  # a tried twice
    assert len(b.calls) == 1  # b answered first try


# ----------------------------------------------------------------------
# All providers exhausted
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_last_exception_bubbles_when_all_exhausted() -> None:
    a = _ScriptedClient([RateLimitError])
    b = _ScriptedClient([ProviderError])
    chain = FallbackChain([a, b])
    with pytest.raises(ProviderError):
        await chain.call(system="s", messages=[])


# ----------------------------------------------------------------------
# Capabilities — intersection rule
# ----------------------------------------------------------------------


def test_capabilities_intersection() -> None:
    a = _ScriptedClient([], capabilities_set={"tools", "caching", "thinking"})
    b = _ScriptedClient([], capabilities_set={"tools", "caching"})
    chain = FallbackChain([a, b])
    assert chain.capabilities() == {"tools", "caching"}


def test_capabilities_empty_intersection() -> None:
    a = _ScriptedClient([], capabilities_set={"tools"})
    b = _ScriptedClient([], capabilities_set={"caching"})
    chain = FallbackChain([a, b])
    assert chain.capabilities() == set()


def test_supports_reflects_intersection() -> None:
    a = _ScriptedClient([], capabilities_set={"tools", "caching"})
    b = _ScriptedClient([], capabilities_set={"tools"})
    chain = FallbackChain([a, b])
    assert chain.supports("tools") is True
    assert chain.supports("caching") is False  # b doesn't support


# ----------------------------------------------------------------------
# Optional methods — capability-intersection rule
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_with_cache_raises_if_not_all_support() -> None:
    a = _ScriptedClient([], capabilities_set={"caching"})
    b = _ScriptedClient([], capabilities_set=set())
    chain = FallbackChain([a, b])
    with pytest.raises(CapabilityNotSupported, match="caching"):
        await chain.call_with_cache(system="s", messages=[], cache_breakpoints=[0])


@pytest.mark.asyncio
async def test_call_with_thinking_raises_if_not_all_support() -> None:
    a = _ScriptedClient([], capabilities_set={"thinking"})
    b = _ScriptedClient([], capabilities_set=set())
    chain = FallbackChain([a, b])
    with pytest.raises(CapabilityNotSupported, match="thinking"):
        await chain.call_with_thinking(system="s", messages=[], thinking_budget_tokens=100)


def test_stream_raises_unsupported() -> None:
    a = _ScriptedClient([])
    chain = FallbackChain([a])
    with pytest.raises(CapabilityNotSupported, match="streaming"):
        chain.stream(system="s", messages=[])


# ----------------------------------------------------------------------
# close() cascades
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_cascades_to_every_provider() -> None:
    a = _ScriptedClient([])
    b = _ScriptedClient([])
    c = _ScriptedClient([])
    chain = FallbackChain([a, b, c])
    await chain.close()
    assert a.closed is True
    assert b.closed is True
    assert c.closed is True


@pytest.mark.asyncio
async def test_close_swallows_individual_errors() -> None:
    """A failing close on one provider must not block close of the
    others — best-effort cleanup."""

    class _BrokenCloser(_ScriptedClient):
        async def close(self) -> None:
            raise RuntimeError("close failed")

    a = _BrokenCloser([])
    b = _ScriptedClient([])
    chain = FallbackChain([a, b])
    await chain.close()  # must not raise
    assert b.closed is True


# ----------------------------------------------------------------------
# Diagnostics
# ----------------------------------------------------------------------


def test_last_used_provider_starts_none() -> None:
    chain = FallbackChain([_ScriptedClient([])])
    assert chain.last_used_provider is None


@pytest.mark.asyncio
async def test_last_used_provider_tracks_index() -> None:
    a = _ScriptedClient([RateLimitError])
    b = _ScriptedClient([_response()])
    chain = FallbackChain([a, b])
    await chain.call(system="s", messages=[])
    assert chain.last_used_provider == 1
