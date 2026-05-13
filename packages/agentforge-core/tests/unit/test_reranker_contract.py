"""Unit tests for the `Reranker` ABC (feat-021)."""

from __future__ import annotations

import pytest
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.testing import run_reranker_conformance
from agentforge_core.values.vector import VectorMatch


class _ReverseReranker(Reranker):
    """Reference impl for the conformance suite: returns candidates in
    reverse order, with scores re-derived from rank position so they
    fit the `[0, 1]` contract."""

    async def rerank(
        self,
        query: str,
        candidates: list[VectorMatch],
        *,
        top_k: int | None = None,
    ) -> list[VectorMatch]:
        del query
        if top_k is not None and top_k < 1:
            msg = f"top_k must be >= 1, got {top_k}"
            raise ValueError(msg)
        if not candidates:
            return []
        reversed_ = list(reversed(candidates))
        n = len(reversed_)
        rescored = [
            VectorMatch(
                id=m.id,
                text=m.text,
                metadata=m.metadata,
                score=(n - i) / n,
            )
            for i, m in enumerate(reversed_)
        ]
        if top_k is not None:
            return rescored[:top_k]
        return rescored

    async def close(self) -> None:
        return None

    def capabilities(self) -> set[str]:
        return {"local"}


class _IdentityReranker(Reranker):
    """Reranker that hands back exactly what came in (passes through
    scores unchanged)."""

    async def rerank(
        self,
        query: str,
        candidates: list[VectorMatch],
        *,
        top_k: int | None = None,
    ) -> list[VectorMatch]:
        del query
        if top_k is not None and top_k < 1:
            msg = f"top_k must be >= 1, got {top_k}"
            raise ValueError(msg)
        if not candidates:
            return []
        sorted_ = sorted(candidates, key=lambda m: m.score, reverse=True)
        if top_k is not None:
            return sorted_[:top_k]
        return sorted_

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_reverse_reranker_passes_conformance() -> None:
    await run_reranker_conformance(_ReverseReranker())


@pytest.mark.asyncio
async def test_identity_reranker_passes_conformance() -> None:
    await run_reranker_conformance(_IdentityReranker())


@pytest.mark.asyncio
async def test_capabilities_default_empty_set() -> None:
    assert _IdentityReranker().capabilities() == set()
    assert _IdentityReranker().supports("local") is False


@pytest.mark.asyncio
async def test_capabilities_override_propagates() -> None:
    assert _ReverseReranker().capabilities() == {"local"}
    assert _ReverseReranker().supports("local") is True
    assert _ReverseReranker().supports("managed") is False
