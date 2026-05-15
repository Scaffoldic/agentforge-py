"""Voyage runner Protocol + production SDK wrapper."""

from __future__ import annotations

from typing import Any, Protocol


class VoyageRunner(Protocol):
    """Lifecycle Protocol for one Voyage embed call."""

    async def embed(
        self,
        *,
        texts: list[str],
        model: str,
        input_type: str | None,
        output_dimension: int | None,
        timeout_s: float,
    ) -> dict[str, Any]:  # pragma: no cover
        """Embed a batch of texts. Returns `{"embeddings": [[...], ...],
        "total_tokens": int}` shape."""
        ...

    async def close(self) -> None:  # pragma: no cover
        ...


class _VoyageSDKRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``voyageai.AsyncClient``."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def embed(
        self,
        *,
        texts: list[str],
        model: str,
        input_type: str | None,
        output_dimension: int | None,
        timeout_s: float,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"texts": texts, "model": model}
        if input_type is not None:
            kwargs["input_type"] = input_type
        if output_dimension is not None:
            kwargs["output_dimension"] = output_dimension
        # voyageai AsyncClient doesn't expose a per-call timeout kwarg
        # in its current API; the SDK's client-level timeout governs.
        _ = timeout_s
        result = await self._client.embed(**kwargs)
        return {
            "embeddings": list(result.embeddings),
            "total_tokens": int(getattr(result, "total_tokens", 0) or 0),
        }

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            maybe = close()
            if hasattr(maybe, "__await__"):
                await maybe


__all__ = ["VoyageRunner"]
