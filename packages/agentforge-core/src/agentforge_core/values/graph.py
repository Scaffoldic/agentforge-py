"""Frozen value types for the `GraphStore` contract.

`GraphNode` and `GraphEdge` are what callers upsert; `GraphPattern`
(composed of `GraphSegment`) is the query DSL `match()` accepts; `Path`
is what `match()` and `traverse()` return. All immutable Pydantic
models — safe to pass across async boundaries without aliasing bugs.

Per ADR-0007 these shapes are part of the framework's locked surface.
Adding a field is a minor bump; removing or renaming requires a major
bump.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GraphNode(BaseModel):
    """One node in a `GraphStore`.

    Attributes:
        id: Caller-controlled identifier. Re-upserting an existing id
            replaces the prior record (write-through, not append).
        labels: Type tags. Empty tuple is allowed — nodes without
            labels are still queryable by id and properties. Order is
            insignificant; drivers may sort internally.
        properties: Free-form key-value attributes. Used by
            `GraphPattern.node_filters` for AND-style equality
            filtering during `match()`.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    id: str = Field(min_length=1)
    labels: tuple[str, ...] = Field(default_factory=tuple)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """One directed edge in a `GraphStore`.

    Attributes:
        src: Source node id. Drivers must reject edges referring to
            absent nodes (raise `ValueError`); `add_node` first.
        dst: Destination node id. Same constraint as `src`.
        edge_type: Relationship type, e.g. `"CITES"`, `"AUTHORED_BY"`.
            Required and non-empty (the field name `type` would shadow
            the builtin, hence `edge_type`).
        properties: Free-form key-value attributes on the edge itself
            (weight, timestamp, etc.).
    """

    model_config = ConfigDict(frozen=True, strict=True)

    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    edge_type: str = Field(min_length=1)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphSegment(BaseModel):
    """One hop in a `GraphPattern`.

    `None` for `src_label`, `edge_type`, or `dst_label` is a wildcard
    at that position. `direction` controls how the edge is matched
    against the underlying store — `"out"` is the default and matches
    `src -> dst`; `"in"` matches `dst <- src` (i.e. reversed); `"any"`
    matches either direction.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    src_label: str | None = None
    edge_type: str | None = None
    dst_label: str | None = None
    direction: Literal["out", "in", "any"] = "out"


class GraphPattern(BaseModel):
    """A chained pattern for `GraphStore.match`.

    `segments` is the ordered chain of hops (length 1 = one edge).
    `node_filters` is an optional sequence of equality filters indexed
    by node-position: position 0 is the start node, position 1 is the
    destination of segment 0, position 2 is the destination of segment
    1, and so on. Length must be either 0 (no filters), or `len(segments) + 1`.

    Example: matching `(:Doc {topic="ml"})-[:CITES]->(:Doc)` becomes
    ``GraphPattern(segments=(GraphSegment(src_label="Doc",
    edge_type="CITES", dst_label="Doc"),),
    node_filters=({"topic": "ml"}, {}))``.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    segments: tuple[GraphSegment, ...] = Field(min_length=1)
    node_filters: tuple[dict[str, Any], ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _filters_match_segments(self) -> GraphPattern:
        if self.node_filters and len(self.node_filters) != len(self.segments) + 1:
            msg = (
                f"node_filters length {len(self.node_filters)} must equal "
                f"len(segments) + 1 = {len(self.segments) + 1} (one filter "
                f"per node position) or be empty"
            )
            raise ValueError(msg)
        return self


class Path(BaseModel):
    """An ordered chain of nodes connected by edges.

    Returned by both `match()` and `traverse()`. Invariants enforced:
      - at least one node
      - `len(edges) == len(nodes) - 1`
      - each edge `i` connects `nodes[i]` to `nodes[i+1]` (drivers
        respect this; the value type doesn't re-check the topology
        beyond length, since per-edge id checking would require
        property-level equality which is wasteful)
    """

    model_config = ConfigDict(frozen=True, strict=True)

    nodes: tuple[GraphNode, ...] = Field(min_length=1)
    edges: tuple[GraphEdge, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _edges_count_matches_nodes(self) -> Path:
        expected = len(self.nodes) - 1
        if len(self.edges) != expected:
            msg = f"edges length {len(self.edges)} must equal len(nodes) - 1 = {expected}"
            raise ValueError(msg)
        return self
