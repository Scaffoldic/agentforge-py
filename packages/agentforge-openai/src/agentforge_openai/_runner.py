"""OpenAI runner Protocol + production SDK wrapper.

Protocol abstracts the three SDK calls we make (chat completions,
chat completions stream, embeddings) so unit tests don't need
`openai` in the dev venv. Production `_OpenAISDKRunner` wraps
`openai.AsyncOpenAI` under `# pragma: no cover`.
"""

from __future__ import annotations

from typing import Any, Protocol, cast


class OpenAIRunner(Protocol):
    """Lifecycle Protocol for OpenAI API calls."""

    async def chat_completions_create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:  # pragma: no cover
        """Issue a non-streaming chat.completions.create call."""
        ...

    async def chat_completions_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> Any:  # pragma: no cover
        """Open a streaming chat.completions.create call.

        Returns an async iterator over per-event chunks.
        """
        ...

    async def embeddings_create(
        self,
        *,
        model: str,
        inputs: list[str],
        timeout_s: float,
        dimensions: int | None = None,
    ) -> dict[str, Any]:  # pragma: no cover
        """Issue an embeddings.create call."""
        ...

    async def close(self) -> None:  # pragma: no cover
        """Release the underlying HTTP client."""
        ...


class _OpenAISDKRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``openai.AsyncOpenAI``."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def chat_completions_create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "timeout": timeout_s,
        }
        if tools:
            kwargs["tools"] = tools
        if extra:
            kwargs.update(extra)
        result = await self._client.chat.completions.create(**kwargs)
        return cast("dict[str, Any]", result.model_dump(mode="python", exclude_none=False))

    async def chat_completions_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "timeout": timeout_s,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
        if extra:
            kwargs.update(extra)
        return await self._client.chat.completions.create(**kwargs)

    async def embeddings_create(
        self,
        *,
        model: str,
        inputs: list[str],
        timeout_s: float,
        dimensions: int | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "input": inputs,
            "timeout": timeout_s,
        }
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        result = await self._client.embeddings.create(**kwargs)
        return cast("dict[str, Any]", result.model_dump(mode="python", exclude_none=False))

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            await close()


__all__ = ["OpenAIRunner"]
