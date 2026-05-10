"""Unit tests for the `GraphStore` value types."""

from __future__ import annotations

import pytest
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    GraphSegment,
    Path,
)
from pydantic import ValidationError

# ---- GraphNode ----


def test_graph_node_basic() -> None:
    node = GraphNode(id="paper:1", labels=("Doc", "Paper"), properties={"year": 2017})
    assert node.id == "paper:1"
    assert node.labels == ("Doc", "Paper")
    assert node.properties == {"year": 2017}


def test_graph_node_defaults_empty_labels_and_properties() -> None:
    node = GraphNode(id="x")
    assert node.labels == ()
    assert node.properties == {}


def test_graph_node_rejects_empty_id() -> None:
    with pytest.raises(ValidationError):
        GraphNode(id="", labels=("Doc",))


def test_graph_node_is_frozen() -> None:
    node = GraphNode(id="x")
    with pytest.raises(ValidationError):
        node.id = "mutated"  # type: ignore[misc]


def test_graph_node_labels_must_be_tuple() -> None:
    """Strict mode rejects lists for tuple-typed fields — forces
    callers to think about immutability."""
    with pytest.raises(ValidationError):
        GraphNode(id="x", labels=["Doc"])  # type: ignore[arg-type]


# ---- GraphEdge ----


def test_graph_edge_basic() -> None:
    edge = GraphEdge(src="a", dst="b", edge_type="CITES", properties={"weight": 1.0})
    assert edge.src == "a"
    assert edge.dst == "b"
    assert edge.edge_type == "CITES"
    assert edge.properties == {"weight": 1.0}


def test_graph_edge_rejects_empty_endpoints() -> None:
    with pytest.raises(ValidationError):
        GraphEdge(src="", dst="b", edge_type="X")
    with pytest.raises(ValidationError):
        GraphEdge(src="a", dst="", edge_type="X")


def test_graph_edge_rejects_empty_type() -> None:
    with pytest.raises(ValidationError):
        GraphEdge(src="a", dst="b", edge_type="")


def test_graph_edge_is_frozen() -> None:
    edge = GraphEdge(src="a", dst="b", edge_type="X")
    with pytest.raises(ValidationError):
        edge.edge_type = "Y"  # type: ignore[misc]


# ---- GraphSegment ----


def test_graph_segment_full_wildcard_default() -> None:
    seg = GraphSegment()
    assert seg.src_label is None
    assert seg.edge_type is None
    assert seg.dst_label is None
    assert seg.direction == "out"


def test_graph_segment_concrete() -> None:
    seg = GraphSegment(src_label="Doc", edge_type="CITES", dst_label="Doc", direction="in")
    assert seg.direction == "in"


def test_graph_segment_rejects_invalid_direction() -> None:
    with pytest.raises(ValidationError):
        GraphSegment(direction="sideways")  # type: ignore[arg-type]


# ---- GraphPattern ----


def test_graph_pattern_one_segment() -> None:
    p = GraphPattern(segments=(GraphSegment(edge_type="CITES"),))
    assert len(p.segments) == 1
    assert p.node_filters == ()


def test_graph_pattern_rejects_empty_segments() -> None:
    with pytest.raises(ValidationError):
        GraphPattern(segments=())


def test_graph_pattern_filters_must_match_segments_plus_one() -> None:
    """Two segments → three node positions → exactly three filters
    (or zero, meaning no filters at all)."""
    GraphPattern(
        segments=(GraphSegment(), GraphSegment()),
        node_filters=({"x": 1}, {}, {"y": 2}),
    )

    with pytest.raises(ValidationError):
        GraphPattern(
            segments=(GraphSegment(), GraphSegment()),
            node_filters=({"x": 1}, {}),
        )


def test_graph_pattern_filters_zero_is_allowed() -> None:
    """`node_filters=()` means no filtering — explicit zero is the
    common case and must not trigger the length-mismatch validator."""
    p = GraphPattern(
        segments=(GraphSegment(), GraphSegment(), GraphSegment()),
        node_filters=(),
    )
    assert p.node_filters == ()


# ---- Path ----


def test_path_single_node() -> None:
    p = Path(nodes=(GraphNode(id="a"),))
    assert len(p.nodes) == 1
    assert p.edges == ()


def test_path_two_node_one_edge() -> None:
    p = Path(
        nodes=(GraphNode(id="a"), GraphNode(id="b")),
        edges=(GraphEdge(src="a", dst="b", edge_type="X"),),
    )
    assert len(p.edges) == 1


def test_path_rejects_edge_count_mismatch() -> None:
    with pytest.raises(ValidationError):
        Path(
            nodes=(GraphNode(id="a"), GraphNode(id="b")),
            edges=(),
        )
    with pytest.raises(ValidationError):
        Path(
            nodes=(GraphNode(id="a"),),
            edges=(GraphEdge(src="a", dst="a", edge_type="self"),),
        )


def test_path_rejects_no_nodes() -> None:
    with pytest.raises(ValidationError):
        Path(nodes=())


def test_path_is_frozen() -> None:
    p = Path(nodes=(GraphNode(id="a"),))
    with pytest.raises(ValidationError):
        p.nodes = (GraphNode(id="b"),)  # type: ignore[misc]
