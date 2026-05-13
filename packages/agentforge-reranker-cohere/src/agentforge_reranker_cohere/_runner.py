"""Cohere runner Protocol + production SDK wrapper.

The Protocol abstracts the single SDK call we make so unit
tests don't need the SDK in the dev venv. Production
`_CohereClientRunner` wraps `cohere.Client` under
`# pragma: no cover`.
"""

from __future__ import annotations

from typing import Any, Protocol


class CohereRunner(Protocol):
    """Lifecycle Protocol for one Cohere Rerank call."""

    def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        model: str,
        top_n: int,
    ) -> list[tuple[int, float]]:  # pragma: no cover
        """Score each ``(query, document)`` pair.

        Returns a list of ``(original_index, score)`` tuples in the
        order Cohere returned them (already sorted desc by score).
        ``top_n`` caps the result count server-side.
        """
        ...

    def close(self) -> None:  # pragma: no cover
        """Release any held HTTP session."""
        ...


class _CohereClientRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``cohere.Client``."""

    def __init__(self, client: Any, *, timeout_s: float = 30.0) -> None:
        self._client = client
        self._timeout_s = timeout_s

    def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        model: str,
        top_n: int,
    ) -> list[tuple[int, float]]:
        response = self._client.rerank(
            query=query,
            documents=documents,
            model=model,
            top_n=top_n,
        )
        return [(item.index, float(item.relevance_score)) for item in response.results]

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


__all__ = ["CohereRunner"]
