"""Voyage runner Protocol + production SDK wrapper."""

from __future__ import annotations

from typing import Any, Protocol


class VoyageRunner(Protocol):
    """Lifecycle Protocol for one Voyage rerank call."""

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
        descending-score order. ``top_k`` caps the response
        size server-side.
        """
        ...

    def close(self) -> None:  # pragma: no cover
        """Release any held HTTP session."""
        ...


class _VoyageClientRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``voyageai.Client``."""

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
            query=query,
            documents=documents,
            model=model,
            top_k=top_k,
        )
        return [(item.index, float(item.relevance_score)) for item in response.results]

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


__all__ = ["VoyageRunner"]
