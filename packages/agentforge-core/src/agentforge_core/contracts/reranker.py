"""`Reranker` — locked cross-encoder reranking ABC (feat-021).

A reranker scores `(query, candidate)` pairs directly, rather
than indexing then matching like a `VectorStore`. The standard
production RAG pattern is: pull the top-`K * factor` candidates
from a `VectorStore` for recall, then rerank to `top_k` for
precision. The framework owns the contract so swapping
SentenceTransformers ↔ Cohere ↔ Voyage is a config change, not
a rewrite.

Per ADR-0007 the surface is locked at v0.2: adding a method is
a major version bump. Optional capabilities layer the same way
as `VectorStore` / `LLMClient` capabilities — declared via
`capabilities()` and gated by callers.

Conformance: every shipped or third-party reranker must pass
`run_reranker_conformance(reranker)` (ships alongside this
contract).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentforge_core.values.vector import VectorMatch


class Reranker(ABC):
    """Re-orders a candidate list by relevance to a query.

    Implementations:
      - return a *new* list (callers may inspect the input list
        after the call; mutation is forbidden)
      - sort descending by the reranker's own relevance score
      - replace each returned `VectorMatch.score` with the
        reranker's normalised score (still in `[0, 1]`); other
        fields (`id`, `text`, `metadata`) pass through unchanged
      - when ``top_k`` is None, return all candidates re-sorted
      - when set, truncate to the top ``top_k`` after sorting

    Cross-driver invariants enforced by the conformance suite:
      - len(rerank(...)) == min(len(candidates), top_k or ∞)
      - 0 ≤ result[i].score ≤ 1 for every returned match
      - result is sorted descending by score
      - empty `candidates` returns `[]`
    """

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[VectorMatch],
        *,
        top_k: int | None = None,
    ) -> list[VectorMatch]:
        """Re-sort `candidates` by relevance to `query`.

        Args:
            query: Free-text query to score candidates against.
            candidates: Output of an earlier `VectorStore.search`
                (or any list of `VectorMatch`). Read-only — the
                reranker must not mutate the input.
            top_k: When set, truncate the result to this many
                items. None returns all candidates re-sorted.

        Returns:
            A new list of `VectorMatch`, sorted descending by the
            reranker's relevance score (replacing the original
            `score`). Other fields pass through unchanged.

        Raises:
            ValueError: ``top_k < 1`` when not None.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release backing resources (model handles, HTTP clients)."""

    def capabilities(self) -> set[str]:
        """Optional capabilities this reranker declares.

        Default empty set. Closed vocabulary (additions are minor
        bumps): ``"local"`` (runs offline, no network calls),
        ``"managed"`` (calls an external API), ``"batched"``
        (`rerank` internally batches the candidate pairs).
        """
        return set()

    def supports(self, capability: str) -> bool:
        """True if this reranker declares the given capability."""
        return capability in self.capabilities()
