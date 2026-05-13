"""In-memory `MixedbreadRunner` for unit tests + downstream integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _RerankCall:
    query: str
    documents: list[str]
    model: str
    top_k: int


class FakeMixedbreadRunner:
    """In-memory recorder of every Mixedbread rerank call."""

    def __init__(self, results: list[tuple[int, float]] | None = None) -> None:
        self._results = list(results or [])
        self.rerank_calls: list[_RerankCall] = []
        self.closed = False

    def set_results(self, results: list[tuple[int, float]]) -> None:
        self._results = list(results)

    def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        model: str,
        top_k: int,
    ) -> list[tuple[int, float]]:
        self.rerank_calls.append(
            _RerankCall(query=query, documents=list(documents), model=model, top_k=top_k),
        )
        return self._results[:top_k]

    def close(self) -> None:
        self.closed = True


__all__ = ["FakeMixedbreadRunner"]
