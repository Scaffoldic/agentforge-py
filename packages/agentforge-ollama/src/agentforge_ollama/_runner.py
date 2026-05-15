"""Ollama runner Protocol + production SDK wrapper."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, cast


class OllamaRunner(Protocol):
    """Lifecycle Protocol for Ollama API calls."""

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:  # pragma: no cover
        ...

    def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:  # pragma: no cover
        ...

    async def embed(
        self,
        *,
        model: str,
        inputs: list[str],
        timeout_s: float,
    ) -> dict[str, Any]:  # pragma: no cover
        ...

    async def close(self) -> None:  # pragma: no cover
        ...


class _OllamaSDKRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``ollama.AsyncClient``."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            kwargs["tools"] = tools
        if options:
            kwargs["options"] = options
        # `ollama.AsyncClient` carries timeout on the client; we
        # accept and ignore the per-call value to keep the contract
        # uniform.
        _ = timeout_s
        result = await self._client.chat(**kwargs)
        if hasattr(result, "model_dump"):
            return cast("dict[str, Any]", result.model_dump(mode="python", exclude_none=False))
        return cast("dict[str, Any]", dict(result))

    def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
        if options:
            kwargs["options"] = options
        _ = timeout_s
        return self._iterate_stream(kwargs)

    async def _iterate_stream(self, kwargs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        async for chunk in await self._client.chat(**kwargs):
            yield (
                dict(chunk)
                if not hasattr(chunk, "model_dump")
                else chunk.model_dump(
                    mode="python",
                    exclude_none=False,
                )
            )

    async def embed(
        self,
        *,
        model: str,
        inputs: list[str],
        timeout_s: float,
    ) -> dict[str, Any]:
        _ = timeout_s
        result = await self._client.embed(model=model, input=inputs)
        if hasattr(result, "model_dump"):
            return cast("dict[str, Any]", result.model_dump(mode="python", exclude_none=False))
        return cast("dict[str, Any]", dict(result))

    async def close(self) -> None:
        close = getattr(self._client, "_client", None)
        # ollama.AsyncClient holds an httpx.AsyncClient as `_client`.
        aclose = getattr(close, "aclose", None) if close is not None else None
        if callable(aclose):
            await aclose()


__all__ = ["OllamaRunner"]
