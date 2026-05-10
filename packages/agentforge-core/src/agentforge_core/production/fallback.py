"""`FallbackChain` — cross-provider failover wrapping multiple
`LLMClient`s (feat-007).

Implements the `LLMClient` ABC, so any strategy that accepts an
`LLMClient` accepts a chain transparently.

Usage:

    from agentforge import Agent, FallbackChain

    chain = FallbackChain(
        [
            "anthropic:claude-sonnet-4.7",
            "bedrock:anthropic.claude-sonnet-4.7",
            "openai:gpt-4o",
        ],
        retry_on=(RateLimitError, ProviderError),
        attempts_per_provider=1,
    )
    agent = Agent(model=chain, tools=[...])

Behaviour:
  - On `retry_on` exception → try next provider (after retrying the
    current provider `attempts_per_provider` times).
  - Last provider's exception bubbles up if every provider exhausts.
  - `last_used_provider` tracks the index of the provider that
    answered the most recent call (diagnostic only).
  - `capabilities()` returns the **intersection** of every wrapped
    provider's capabilities — a chain can only honestly claim what
    every fallback can deliver.
  - `call_with_cache` / `call_with_thinking` raise
    `CapabilityNotSupported` unless every wrapped provider declares
    the capability.
  - `close()` cascades in reverse-construction order.

Out of scope (v0.1):
  - Streaming (`stream`) — not yet supported by `FallbackChain`;
    callers using streaming should pick a single provider.
  - Provider-level retry backoff — providers handle their own
    retries internally.
  - Per-call `retry_on` override — chain-level configuration only.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production.exceptions import (
    CapabilityNotSupported,
    ModuleError,
    ProviderError,
    RateLimitError,
)
from agentforge_core.resolver import Resolver, parse_model_string
from agentforge_core.values.messages import LLMResponse, Message, ToolSpec

log = logging.getLogger(__name__)

_DEFAULT_RETRY_ON: tuple[type[Exception], ...] = (RateLimitError, ProviderError)
_DEFAULT_ATTEMPTS_PER_PROVIDER = 1


class FallbackChain(LLMClient):
    """Wrap multiple `LLMClient`s with cross-provider failover.

    Args:
        providers: A non-empty list of providers. Each entry is
            either a model string (`"<provider>:<model_id>"`,
            resolved via the global `Resolver`) or a typed
            `LLMClient` instance.
        retry_on: Exception types that trigger a fallback to the
            next provider. Default: `(RateLimitError, ProviderError)`.
            Other exceptions (e.g. `AuthenticationError`) bubble
            immediately — falling back on those is usually wrong.
        attempts_per_provider: How many times to retry the *current*
            provider before moving to the next. Default 1 (no
            retry; first failure → next provider).

    Raises:
        ValueError: empty providers list, non-positive
            `attempts_per_provider`, or an unrecognised provider
            string.
    """

    def __init__(
        self,
        providers: list[str | LLMClient],
        *,
        retry_on: tuple[type[Exception], ...] = _DEFAULT_RETRY_ON,
        attempts_per_provider: int = _DEFAULT_ATTEMPTS_PER_PROVIDER,
    ) -> None:
        if not providers:
            msg = "FallbackChain requires at least one provider"
            raise ValueError(msg)
        if attempts_per_provider < 1:
            msg = f"attempts_per_provider must be >= 1, got {attempts_per_provider}"
            raise ValueError(msg)
        self._clients: list[LLMClient] = [_resolve_provider(p) for p in providers]
        self._retry_on = retry_on
        self._attempts_per_provider = attempts_per_provider
        self._last_used_provider: int | None = None

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def last_used_provider(self) -> int | None:
        """Index (0-based) of the provider that answered the most
        recent call. `None` until the first call succeeds."""
        return self._last_used_provider

    @property
    def providers(self) -> tuple[LLMClient, ...]:
        """Resolved providers in chain order. Useful for tests."""
        return tuple(self._clients)

    # ------------------------------------------------------------------
    # LLMClient surface
    # ------------------------------------------------------------------

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        return await self._dispatch_with_fallback("call", system, messages, tools=tools)

    async def close(self) -> None:
        """Close every wrapped provider in reverse-construction order.

        Reverse order so a partial-construction failure during
        `__init__` doesn't leak resources held by earlier providers.
        Exceptions during close are logged and swallowed; the goal
        is best-effort cleanup, not failure.
        """
        for client in reversed(self._clients):
            try:
                await client.close()
            except Exception:
                log.exception(
                    "FallbackChain: error closing %s; continuing",
                    type(client).__name__,
                )

    def capabilities(self) -> set[str]:
        """Intersection of every wrapped provider's capabilities.

        A chain can only honestly claim a capability that every
        fallback can deliver — otherwise a fallback might fail to
        honour a feature the caller relied on declaring.
        """
        if not self._clients:
            return set()
        common = set(self._clients[0].capabilities())
        for client in self._clients[1:]:
            common &= client.capabilities()
        return common

    # ------------------------------------------------------------------
    # Optional capabilities — capability-intersection rule
    # ------------------------------------------------------------------

    async def call_with_cache(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        cache_breakpoints: list[int],
    ) -> LLMResponse:
        if "caching" not in self.capabilities():
            msg = (
                "FallbackChain does not support 'caching'. Every "
                "wrapped provider must declare the capability for the "
                "chain to honour it; check chain.supports('caching') "
                "before calling."
            )
            raise CapabilityNotSupported(msg)
        return await self._dispatch_with_fallback(
            "call_with_cache",
            system,
            messages,
            tools=tools,
            cache_breakpoints=cache_breakpoints,
        )

    async def call_with_thinking(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        thinking_budget_tokens: int,
    ) -> LLMResponse:
        if "thinking" not in self.capabilities():
            msg = (
                "FallbackChain does not support 'thinking'. Every "
                "wrapped provider must declare the capability for the "
                "chain to honour it; check chain.supports('thinking') "
                "before calling."
            )
            raise CapabilityNotSupported(msg)
        return await self._dispatch_with_fallback(
            "call_with_thinking",
            system,
            messages,
            tools=tools,
            thinking_budget_tokens=thinking_budget_tokens,
        )

    def stream(
        self,
        system: str,  # noqa: ARG002 — interface compatibility; we raise unconditionally
        messages: list[Message],  # noqa: ARG002
        tools: list[ToolSpec] | None = None,  # noqa: ARG002
    ) -> AsyncIterator[Any]:
        """Streaming is not supported on `FallbackChain` in v0.1.

        Streaming with cross-provider fallback semantics is genuinely
        harder than the unary call: events from provider N might
        partially arrive before a fallback to N+1 kicks in, leaving
        the caller with incoherent partial output. Callers needing
        streaming should pick a single provider.
        """
        msg = (
            "FallbackChain does not support 'streaming' in v0.1. "
            "Pick a single provider for streaming use cases."
        )
        raise CapabilityNotSupported(msg)

    # ------------------------------------------------------------------
    # Internal — fallback dispatch
    # ------------------------------------------------------------------

    async def _dispatch_with_fallback(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> LLMResponse:
        """Iterate providers; for each, try `attempts_per_provider`
        times; on `retry_on` exception move to the next provider.

        The last provider's exception bubbles up if every provider
        is exhausted.
        """
        last_exc: Exception | None = None
        for index, client in enumerate(self._clients):
            method = getattr(client, method_name)
            for attempt in range(self._attempts_per_provider):
                try:
                    response: LLMResponse = await method(*args, **kwargs)
                except self._retry_on as exc:
                    last_exc = exc
                    log.warning(
                        "FallbackChain: provider %d/%d (%s) raised %s (attempt %d/%d); %s",
                        index + 1,
                        len(self._clients),
                        type(client).__name__,
                        type(exc).__name__,
                        attempt + 1,
                        self._attempts_per_provider,
                        "trying next provider"
                        if attempt + 1 == self._attempts_per_provider
                        else "retrying",
                    )
                    continue
                else:
                    self._last_used_provider = index
                    return response
        # Every provider exhausted.
        assert last_exc is not None
        raise last_exc


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _resolve_provider(provider: Any) -> LLMClient:
    """Turn a `str` model spec or `LLMClient` instance into an
    `LLMClient` instance via the global resolver.

    Accepts `Any` (not `str | LLMClient`) so the runtime
    `isinstance` guards remain reachable for type-checkers — the
    public `FallbackChain.__init__` signature is the typed gate;
    this internal helper hardens against accidental mistypes.
    """
    if isinstance(provider, LLMClient):
        return provider
    if not isinstance(provider, str):
        msg = f"FallbackChain providers must be str or LLMClient, got {type(provider).__name__}"
        raise TypeError(msg)
    name, model_id = parse_model_string(provider)
    try:
        cls = Resolver.global_().resolve("providers", name)
    except ModuleError as exc:
        msg = (
            f"FallbackChain: no LLM provider registered for {name!r}. "
            f"Install agentforge-{name} (e.g. "
            f"`uv add agentforge-{name}`) or pass a typed LLMClient "
            f"instance instead of the {provider!r} string."
        )
        raise ValueError(msg) from exc
    instance = cls(model_id=model_id)
    if not isinstance(instance, LLMClient):
        msg = (
            f"FallbackChain: resolved provider {name!r} ({cls.__name__}) "
            f"does not implement LLMClient."
        )
        raise TypeError(msg)
    return instance


__all__ = ["FallbackChain"]
