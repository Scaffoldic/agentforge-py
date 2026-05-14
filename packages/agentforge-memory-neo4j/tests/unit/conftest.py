"""Shared fakes for `agentforge-memory-neo4j` unit tests.

The driver wraps a `CypherRunner` (see `_runner.py`); production
wraps a real `neo4j.AsyncDriver`, but tests inject `GraphFakeRunner`
or `MemoryFakeRunner` defined here. Each fake interprets the limited
Cypher vocabulary the driver emits and routes it to an in-memory
backing store, so we exercise every code path without spinning up
Neo4j.

Live tests against a real Neo4j live in `tests/integration/` (gated on
`RUN_LIVE_NEO4J=1`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
from agentforge.memory.in_memory import InMemoryStore
from agentforge.memory.in_memory_graph import InMemoryGraphStore
from agentforge_core.values.claim import Claim
from agentforge_core.values.graph import (
    GraphEdge,
    GraphNode,
    GraphPattern,
    GraphSegment,
    Path,
)


@dataclass
class _Query:
    cypher: str
    params: dict[str, Any]


@dataclass
class GraphFakeRunner:
    """Cypher fake — interprets the subset emitted by `Neo4jGraphStore`."""

    backing: InMemoryGraphStore = field(default_factory=InMemoryGraphStore)
    queries: list[_Query] = field(default_factory=list)
    closed: bool = False
    # feat-024 migration tracking — mirrors the
    # `:AgentforgeMigration` node label.
    _applied_migrations: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def execute_read(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.queries.append(_Query(cypher, params))
        return await self._dispatch(cypher, params)

    async def execute_write(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.queries.append(_Query(cypher, params))
        return await self._dispatch(cypher, params)

    async def close(self) -> None:
        self.closed = True

    async def _dispatch(  # noqa: PLR0911, PLR0912 — dispatch table over Cypher shapes
        self, cypher: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        c = " ".join(cypher.split())
        if c.startswith("CREATE CONSTRAINT") or c.startswith("CREATE INDEX"):
            return []
        # feat-024 migration tracking — recognise the MATCH/CREATE
        # shapes the migrator emits against `:AgentforgeMigration`.
        if "MATCH (m:AgentforgeMigration)" in c:
            return list(self._applied_migrations.values())
        if "CREATE (m:AgentforgeMigration" in c:
            self._applied_migrations[params["id"]] = {
                "id": params["id"],
                "name": params["name"],
                "checksum": params["checksum"],
                "applied_at": None,
            }
            return []
        if "MERGE (n:AfNode" in c and "SET n = $properties" in c:
            await self.backing.add_node(
                GraphNode(
                    id=params["id"],
                    labels=tuple(params["labels"]),
                    properties=dict(params["properties"]),
                )
            )
            return []
        if "MATCH (s:AfNode" in c and "MATCH (d:AfNode" in c and "RETURN s, d" in c:
            s = await self.backing.get_node(params["src"])
            d = await self.backing.get_node(params["dst"])
            if s is None or d is None:
                return []
            return [{"s": _node_to_record(s), "d": _node_to_record(d)}]
        if "WHERE n._af_id IN $ids" in c:
            present: list[dict[str, Any]] = []
            for nid in params["ids"]:
                node = await self.backing.get_node(nid)
                if node is not None:
                    present.append({"id": nid})
            return present
        if "MERGE (s)-[r:AF_EDGE" in c and "SET r = $properties" in c:
            await self.backing.add_edge(
                GraphEdge(
                    src=params["src"],
                    dst=params["dst"],
                    edge_type=params["edge_type"],
                    properties=dict(params["properties"]),
                )
            )
            return []
        if c == "MATCH (n:AfNode {_af_id: $id}) RETURN n":
            node = await self.backing.get_node(params["id"])
            if node is None:
                return []
            return [{"n": _node_to_record(node)}]
        if "-[r:AF_EDGE]->(other:AfNode)" in c and "RETURN n._af_id" in c:
            edges = await self.backing.get_edges(
                params["id"],
                edge_type=params.get("edge_type"),
                direction="out",
            )
            return [{"src": e.src, "dst": e.dst, "r": _edge_to_record(e)} for e in edges]
        if "<-[r:AF_EDGE]-(other:AfNode)" in c:
            edges = await self.backing.get_edges(
                params["id"],
                edge_type=params.get("edge_type"),
                direction="in",
            )
            return [{"src": e.src, "dst": e.dst, "r": _edge_to_record(e)} for e in edges]
        if c.startswith("MATCH (n0:AfNode)") and "RETURN n0" in c:
            return await self._dispatch_match(c, params)
        if "*1.." in c and "RETURN path" in c:
            return await self._dispatch_traverse(c, params)
        if c.endswith("RETURN count(n) AS c"):
            node = await self.backing.get_node(params["id"])
            return [{"c": 1 if node else 0}]
        if "[r:AF_EDGE]-()" in c and "RETURN count(r) AS c" in c:
            edges = await self.backing.get_edges(params["id"], direction="any")
            return [{"c": len(edges)}]
        if "DETACH DELETE n" in c:
            await self.backing.delete_node(params["id"], cascade=True)
            return []
        if "DELETE n" in c and "DETACH" not in c:
            await self.backing.delete_node(params["id"], cascade=False)
            return []
        if "DELETE r RETURN count(r)" in c:
            removed = await self.backing.delete_edge(
                params["src"], params["dst"], edge_type=params["edge_type"]
            )
            return [{"c": 1 if removed else 0}]
        msg = f"GraphFakeRunner: unrecognised Cypher: {cypher!r}"
        raise AssertionError(msg)

    async def _dispatch_match(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        n_rels = len(re.findall(r"\br\d+\b", cypher))
        segments: list[GraphSegment] = [
            GraphSegment(
                src_label=params.get(f"label_{i}"),
                edge_type=params.get(f"edge_type_{i}"),
                dst_label=params.get(f"label_{i + 1}"),
                direction=_direction_from_cypher(cypher, i),
            )
            for i in range(n_rels)
        ]
        node_filters: list[dict[str, Any]] = [{} for _ in range(n_rels + 1)]
        for i in range(n_rels + 1):
            for k, v in params.items():
                m = re.match(rf"prop_{i}_(.+)", k)
                if m:
                    node_filters[i][m.group(1)] = v
        nf_tuple: tuple[dict[str, Any], ...] = (
            () if all(not nf for nf in node_filters) else tuple(node_filters)
        )
        pattern = GraphPattern(segments=tuple(segments), node_filters=nf_tuple)
        paths = await self.backing.match(pattern, limit=params["limit"])
        return [_path_to_columns(p) for p in paths]

    async def _dispatch_traverse(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        m = re.search(r"\*1\.\.(\d+)", cypher)
        max_depth = int(m.group(1)) if m else 3
        edge_types = tuple(params["edge_types"]) if "edge_types" in params else None
        paths = await self.backing.traverse(
            params["start_id"],
            edge_types=edge_types,
            max_depth=max_depth,
            limit=params["limit"],
        )
        return [{"path": _path_to_record(p)} for p in paths]


def _direction_from_cypher(cypher: str, segment_idx: int) -> str:
    rel = f"r{segment_idx}"
    if f"-[{rel}:AF_EDGE]->" in cypher:
        return "out"
    if f"<-[{rel}:AF_EDGE]-" in cypher:
        return "in"
    return "any"


def _node_to_record(node: GraphNode) -> dict[str, Any]:
    record = dict(node.properties)
    record["_af_id"] = node.id
    record["_af_labels"] = list(node.labels)
    return record


def _edge_to_record(edge: GraphEdge) -> dict[str, Any]:
    record = dict(edge.properties)
    record["_af_edge_type"] = edge.edge_type
    return record


def _path_to_columns(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, n in enumerate(path.nodes):
        out[f"n{i}"] = _node_to_record(n)
    for i, e in enumerate(path.edges):
        out[f"r{i}"] = _edge_to_record(e)
    return out


def _path_to_record(path: Path) -> dict[str, Any]:
    return {
        "nodes": [_node_to_record(n) for n in path.nodes],
        "relationships": [_edge_to_record(e) for e in path.edges],
    }


@dataclass
class MemoryFakeRunner:
    """Cypher fake for `Neo4jMemoryStore`. Backed by `InMemoryStore`."""

    backing: InMemoryStore = field(default_factory=InMemoryStore)
    queries: list[_Query] = field(default_factory=list)
    supersede_edges: list[tuple[str, str]] = field(default_factory=list)
    closed: bool = False
    # feat-024 migration tracking — mirrors the
    # `:AgentforgeMigration` node label.
    _applied_migrations: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def execute_read(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.queries.append(_Query(cypher, params))
        return await self._dispatch_read(cypher, params)

    async def execute_write(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.queries.append(_Query(cypher, params))
        return await self._dispatch_write(cypher, params)

    async def close(self) -> None:
        self.closed = True

    async def _dispatch_read(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        c = " ".join(cypher.split())
        # feat-024 migration tracking
        if "MATCH (m:AgentforgeMigration)" in c:
            return list(self._applied_migrations.values())
        if c == "MATCH (c:Claim {id: $id}) RETURN c":
            claim = await self.backing.get(params["id"])
            if claim is None:
                return []
            return [{"c": _claim_to_record(claim)}]
        if c.startswith("MATCH (c:Claim)"):
            claims = await self.backing.query(
                project=params.get("project"),
                agent=params.get("agent"),
                category=params.get("category"),
                run_id=params.get("run_id"),
                limit=params.get("limit", 100),
            )
            return [{"c": _claim_to_record(cl)} for cl in claims]
        msg = f"MemoryFakeRunner read: unrecognised Cypher: {cypher!r}"
        raise AssertionError(msg)

    async def _dispatch_write(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        c = " ".join(cypher.split())
        if c.startswith("CREATE CONSTRAINT") or c.startswith("CREATE INDEX"):
            return []
        # feat-024 migration tracking
        if "CREATE (m:AgentforgeMigration" in c:
            self._applied_migrations[params["id"]] = {
                "id": params["id"],
                "name": params["name"],
                "checksum": params["checksum"],
                "applied_at": None,
            }
            return []
        if c.startswith("MERGE (c:Claim {id: $id})"):
            claim = Claim(
                id=params["id"],
                project=params["project"],
                agent=params["agent"],
                run_id=params["run_id"],
                category=params["category"],
                payload=json.loads(params["payload"]),
                supersedes=params["supersedes"],
                created_at=datetime.fromisoformat(params["created_at"]),
            )
            await self.backing.put(claim)
            return []
        if "MERGE (n)-[:SUPERSEDES]->(o)" in c:
            self.supersede_edges.append((params["new"], params["old"]))
            return []
        if c.startswith("MATCH (c:Claim) WHERE") and "DETACH DELETE x" in c:
            older_than = params.get("older_than")
            removed = await self.backing.delete(
                run_id=params.get("run_id"),
                category=params.get("category"),
                older_than=datetime.fromisoformat(older_than) if older_than else None,
            )
            return [{"n": removed}]
        msg = f"MemoryFakeRunner write: unrecognised Cypher: {cypher!r}"
        raise AssertionError(msg)


def _claim_to_record(claim: Claim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "project": claim.project,
        "agent": claim.agent,
        "run_id": claim.run_id,
        "category": claim.category,
        "payload": json.dumps(claim.payload),
        "supersedes": claim.supersedes,
        "created_at": claim.created_at.isoformat(),
    }


@pytest.fixture
def graph_fake_runner() -> GraphFakeRunner:
    return GraphFakeRunner()


@pytest.fixture
def memory_fake_runner() -> MemoryFakeRunner:
    return MemoryFakeRunner()


# ----------------------------------------------------------------------
# VectorFakeRunner — feat-025
# ----------------------------------------------------------------------

from agentforge.memory import InMemoryVectorStore  # noqa: E402
from agentforge_core._bm25 import _BM25Index  # noqa: E402
from agentforge_core.values.vector import VectorItem  # noqa: E402


@dataclass
class VectorFakeRunner:
    """Cypher fake for `Neo4jVectorStore`.

    Routes the Cypher shapes the vector store emits to in-memory
    backings: `InMemoryVectorStore` for upsert/search/delete, a
    `_BM25Index` for the fulltext path. The migrator's tracking-
    table queries are recognised too.
    """

    backing: InMemoryVectorStore = field(default_factory=lambda: InMemoryVectorStore(dimensions=8))
    queries: list[_Query] = field(default_factory=list)
    closed: bool = False
    _bm25: _BM25Index | None = None
    _applied_migrations: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def execute_read(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.queries.append(_Query(cypher, params))
        return await self._dispatch(cypher, params)

    async def execute_write(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        self.queries.append(_Query(cypher, params))
        return await self._dispatch(cypher, params)

    async def close(self) -> None:
        self.closed = True

    async def _dispatch(  # noqa: PLR0911
        self, cypher: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        c = " ".join(cypher.split())
        # Migrations (constraints, vector index, fulltext index, etc.)
        if (
            c.startswith("CREATE CONSTRAINT")
            or c.startswith("CREATE VECTOR INDEX")
            or c.startswith("CREATE FULLTEXT INDEX")
            or c.startswith("CREATE INDEX")
        ):
            return []
        # feat-024 migration tracking
        if "MATCH (m:AgentforgeMigration)" in c:
            return list(self._applied_migrations.values())
        if "CREATE (m:AgentforgeMigration" in c:
            self._applied_migrations[params["id"]] = {
                "id": params["id"],
                "name": params["name"],
                "checksum": params["checksum"],
                "applied_at": None,
            }
            return []
        # Vector upsert
        if "MERGE (n:AfVector" in c:
            self._bm25 = None  # invalidate
            return await self._do_upsert(params)
        # Delete probe
        if c.startswith("MATCH (n:AfVector) WHERE n.af_id IN $ids RETURN"):
            ids = list(params["ids"])
            present: list[dict[str, Any]] = [
                {"id": nid} for nid in ids if await self._backing_has(nid)
            ]
            return present
        # Delete actual
        if c.startswith("MATCH (n:AfVector) WHERE n.af_id IN $ids DETACH DELETE"):
            self._bm25 = None
            await self.backing.delete(list(params["ids"]))
            return []
        # Vector search
        if "db.index.vector.queryNodes" in c:
            return await self._do_vector_search(params)
        # Lexical search
        if "db.index.fulltext.queryNodes" in c:
            return await self._do_lexical_search(params)
        msg = f"VectorFakeRunner: unrecognised Cypher: {cypher!r}"
        raise AssertionError(msg)

    async def _backing_has(self, nid: str) -> bool:
        # InMemoryVectorStore doesn't have a `get`; probe via search.
        # We use the internal dict directly for accuracy.
        return nid in self.backing._items  # type: ignore[attr-defined]

    async def _do_upsert(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        await self.backing.upsert(
            [
                VectorItem(
                    id=params["id"],
                    vector=tuple(params["embedding"]),
                    text=params["text"],
                    metadata=dict(params["metadata"]),
                )
            ]
        )
        return []

    async def _do_vector_search(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        limit = int(params["limit"])
        matches = await self.backing.search(tuple(params["query"]), limit=limit)
        return [
            {"id": m.id, "text": m.text, "metadata": dict(m.metadata), "score": m.score}
            for m in matches
        ]

    async def _do_lexical_search(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        limit = int(params["limit"])
        query = str(params["query"])
        # Build a BM25 index lazily over the backing store's text.
        if self._bm25 is None:
            self._bm25 = _BM25Index()
            for nid, (_vec, text, _meta) in self.backing._items.items():  # type: ignore[attr-defined]
                self._bm25.add(nid, text)
        scored = self._bm25.score(query, limit=max(limit, 1))
        out: list[dict[str, Any]] = []
        for nid, raw in scored:
            _vec, text, meta = self.backing._items[nid]  # type: ignore[attr-defined]
            out.append(
                {
                    "id": nid,
                    "text": text,
                    "metadata": dict(meta),
                    "raw": raw,
                }
            )
        return out


@pytest.fixture
def vector_fake_runner() -> VectorFakeRunner:
    return VectorFakeRunner()
