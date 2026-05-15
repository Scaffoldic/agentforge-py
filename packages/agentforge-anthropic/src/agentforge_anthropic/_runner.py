"""Anthropic runner Protocol + production SDK wrapper.

The Protocol abstracts the single SDK call we make so unit tests
don't need the `anthropic` package in the dev venv. Production
`_AnthropicSDKRunner` wraps `anthropic.AsyncAnthropic` under
`# pragma: no cover`.

The runner exposes a single async `messages_create` entry point
covering the four call modes (plain, cache, thinking, streaming)
distinguished by kwargs. The streaming mode returns the SDK's
own async context-manager stream object — the client iterates
it directly via `__aenter__` / `text_stream` / message accumulator.
"""

from __future__ import annotations

from typing import Any, Protocol, cast


class AnthropicRunner(Protocol):
    """Lifecycle Protocol for one Anthropic Messages call."""

    async def messages_create(
        self,
        *,
        model: str,
        system: str | None,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:  # pragma: no cover
        """Issue a non-streaming Messages call.

        `extra` carries optional kwargs (`thinking`, `metadata`,
        `tool_choice`). Returns a plain dict normalised from the
        SDK's `Message` model.
        """
        ...

    async def messages_stream(
        self,
        *,
        model: str,
        system: str | None,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> Any:  # pragma: no cover
        """Open a streaming Messages call.

        Returns the SDK's async context-manager stream object —
        the client `async with`s it and iterates over event /
        text / tool-use deltas.
        """
        ...

    async def close(self) -> None:  # pragma: no cover
        """Release the underlying HTTP client."""
        ...


class _AnthropicSDKRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``anthropic.AsyncAnthropic``."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def messages_create(
        self,
        *,
        model: str,
        system: str | None,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": timeout_s,
        }
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if extra:
            kwargs.update(extra)
        message = await self._client.messages.create(**kwargs)
        # Normalise the SDK Message model into a plain dict so the
        # client code stays SDK-shape-agnostic.
        return cast("dict[str, Any]", message.model_dump(mode="python", exclude_none=False))

    async def messages_stream(
        self,
        *,
        model: str,
        system: str | None,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": timeout_s,
        }
        if system is not None:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if extra:
            kwargs.update(extra)
        return self._client.messages.stream(**kwargs)

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            await close()


__all__ = ["AnthropicRunner"]
