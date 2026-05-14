"""Retrieval-ergonomics value types (feat-023).

`GraphExpansion` bundles the knobs callers pass when wiring a
`Retriever` with graph-augmented expansion — the GraphStore to
traverse, the hop budget, edge-type filtering, the node property
to use as match text, and the per-hop score decay.

Kept frozen + strict per the framework's value-type policy. The
`store` field tolerates an `ABC` instance via
`arbitrary_types_allowed=True` — `GraphStore` isn't itself a
Pydantic model.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentforge_core.contracts.graph_store import GraphStore


class GraphExpansion(BaseModel):
    """Graph-traversal configuration for :class:`Retriever`
    post-retrieve augmentation (feat-023).

    Attributes:
        store: The `GraphStore` driver to traverse.
            ``VectorMatch.id`` ↔ ``GraphNode.id`` alignment is a
            caller contract; mismatched ids silently skip
            expansion for that seed.
        max_hops: Maximum traversal depth (>= 1). Each hop
            multiplies the candidate set by the average graph
            fan-out — tune cautiously.
        edge_types: If set, restricts traversal to these edge
            types. ``None`` means all edge types.
        text_property: Graph-node property used to populate the
            synthesised ``VectorMatch.text``. Defaults to
            ``"text"``.
        decay: Per-hop score decay factor in ``(0, 1]``. An
            expansion node at depth `d` gets score
            ``seed.score * decay ** d``. Default 0.5.
    """

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        arbitrary_types_allowed=True,
    )

    store: GraphStore
    max_hops: int = Field(default=2, ge=1)
    edge_types: tuple[str, ...] | None = None
    text_property: str = Field(default="text", min_length=1)
    decay: float = Field(default=0.5, gt=0.0, le=1.0)
