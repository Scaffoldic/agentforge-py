"""Unit tests for the `VectorStore` ABC default behaviours.

The ABC itself is abstract, so most behaviour testing happens via the
conformance suite against concrete drivers. Here we cover the
default-method behaviours that don't require a concrete impl.
"""

from __future__ import annotations

from typing import Any

import pytest
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.vector import VectorItem, VectorMatch


class _MinimalStore(VectorStore):
    """Minimal concrete impl with no extra capabilities."""

    def __init__(self, *, dim: int = 4) -> None:
        self._dim = dim

    def dimensions(self) -> int:
        return self._dim

    async def upsert(self, items: list[VectorItem]) -> None: ...

    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        return []

    async def delete(self, ids: list[str]) -> int:
        return 0

    async def close(self) -> None: ...


class _AnnStore(_MinimalStore):
    """Driver that declares native ANN support."""

    def capabilities(self) -> set[str]:
        return {"native_ann"}


# ---- Default capabilities ----


def test_default_store_declares_no_capabilities() -> None:
    store = _MinimalStore()
    assert store.capabilities() == set()
    assert store.supports("native_ann") is False
    assert store.supports("anything") is False


def test_ann_store_declares_native_ann() -> None:
    store = _AnnStore()
    assert store.supports("native_ann") is True
    # Other capabilities still report False.
    assert store.supports("hybrid_search") is False


def test_supports_unknown_capability_is_false() -> None:
    """Per ADR-0009, supports() is honest about unknowns — never
    optimistically True for capabilities the driver hasn't declared."""
    assert _AnnStore().supports("not-a-capability-2026") is False


# ---- ABC enforces required methods ----


def test_abc_rejects_partial_implementation() -> None:
    """Trying to instantiate a subclass missing required methods
    raises TypeError at construction (ABC behaviour)."""

    class _Incomplete(VectorStore):
        async def upsert(self, items: list[VectorItem]) -> None: ...

        # Missing search, delete, close, dimensions.

    with pytest.raises(TypeError, match="abstract"):
        _Incomplete()  # type: ignore[abstract]


# ---- Dimensions accessor ----


def test_dimensions_is_sync() -> None:
    """Callers must be able to size storage without awaiting — the
    contract says so for every driver."""
    store = _MinimalStore(dim=1024)
    assert store.dimensions() == 1024
