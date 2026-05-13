"""In-memory `CohereRunner` for unit tests + downstream integration.

Records every rerank call's args + returns scripted
``(index, score)`` results.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _RerankCall:
    query: str
    documents: list[str]
    model: str
    top_n: int


class FakeCohereRunner:
    """In-memory recorder of every Cohere rerank call."""

    def __init__(self, results: list[tuple[int, float]] | None = None) -> None:
        self._results = list(results or [])
        self.rerank_calls: list[_RerankCall] = []
        self.closed = False

    def set_results(self, results: list[tuple[int, float]]) -> None:
        """Replace the scripted ``(index, score)`` list returned on
        subsequent rerank calls."""
        self._results = list(results)

    def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        model: str,
        top_n: int,
    ) -> list[tuple[int, float]]:
        self.rerank_calls.append(
            _RerankCall(query=query, documents=list(documents), model=model, top_n=top_n),
        )
        # Server-side `top_n` caps the response; mirror that here.
        return self._results[:top_n]

    def close(self) -> None:
        self.closed = True


__all__ = ["FakeCohereRunner"]
