"""Mixedbread runner Protocol + production SDK wrapper."""

from __future__ import annotations

from typing import Any, Protocol


class MixedbreadRunner(Protocol):
    """Lifecycle Protocol for one Mixedbread rerank call."""

    def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        model: str,
        top_k: int,
    ) -> list[tuple[int, float]]:  # pragma: no cover
        """Score each ``(query, document)`` pair.

        Returns a list of ``(original_index, score)`` tuples in
        descending-score order.
        """
        ...

    def close(self) -> None:  # pragma: no cover
        """Release any held HTTP session."""
        ...


class _MixedbreadClientRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``mixedbread_ai.MixedbreadAI``."""

    def __init__(self, client: Any, *, timeout_s: float = 30.0) -> None:
        self._client = client
        self._timeout_s = timeout_s

    def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        model: str,
        top_k: int,
    ) -> list[tuple[int, float]]:
        response = self._client.rerank(
            model=model,
            query=query,
            input=documents,
            top_k=top_k,
        )
        # Mixedbread returns response.data as a list of items
        # carrying `.index` + `.score`.
        return [(item.index, float(item.score)) for item in response.data]

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


__all__ = ["MixedbreadRunner"]
