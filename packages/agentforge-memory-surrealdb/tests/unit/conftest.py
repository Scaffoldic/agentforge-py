"""Shared SurrealQL fake for `agentforge-memory-surrealdb` unit tests.

Production wraps `surrealdb.AsyncSurreal`; tests inject this fake
which interprets the limited SurrealQL vocabulary the drivers emit
and routes operations to in-memory backings (a dict for vectors and
claims, an `InMemoryGraphStore` for the graph). Records every query
for assertion.

Live tests against real SurrealDB live in `tests/integration/`
(gated on `RUN_LIVE_SURREAL=1`).
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
from agentforge.memory.in_memory import InMemoryStore
from agentforge.memory.in_memory_graph import InMemoryGraphStore
from agentforge_core.values.claim import Claim
from agentforge_core.values.graph import GraphEdge, GraphNode


@dataclass
class _Query:
    surrealql: str
    vars: dict[str, Any]


@dataclass
class SurrealFakeRunner:
    """Routes SurrealQL queries to in-memory backings.

    Multi-modal: handles graph (`af_node`, `af_edge`), vector
    (`af_vector`), and claim (`af_claim`) tables. Operation
    detection is regex-based over the queries the drivers actually
    emit — narrow surface, so easier than a real SurrealQL parser.
    """

    graph_backing: InMemoryGraphStore = field(default_factory=InMemoryGraphStore)
    memory_backing: InMemoryStore = field(default_factory=InMemoryStore)
    vectors: OrderedDict[str, dict[str, Any]] = field(default_factory=OrderedDict)
    queries: list[_Query] = field(default_factory=list)
    closed: bool = False

    async def query(  # noqa: PLR0911, PLR0912 — dispatch table over SurrealQL shapes
        self, surrealql: str, vars: dict[str, Any] | None = None
    ) -> list[Any]:
        v = vars or {}
        self.queries.append(_Query(surrealql, v))
        s = " ".join(surrealql.split())
        # ---- DEFINE TABLE / INDEX ----
        if s.startswith("DEFINE TABLE") or "DEFINE INDEX" in s:
            return []

        # ---- GRAPH: af_node ----
        if "UPSERT type::thing('af_node', $id)" in s:
            await self.graph_backing.add_node(
                GraphNode(
                    id=v["id"],
                    labels=tuple(v["labels"]),
                    properties=dict(v["properties"]),
                )
            )
            return []
        if "SELECT * FROM af_node WHERE af_id = $id LIMIT 1" in s:
            n = await self.graph_backing.get_node(v["id"])
            return [_node_record(n)] if n else []
        if "SELECT af_id FROM af_node WHERE af_id IN $ids" in s:
            return [
                {"af_id": nid}
                for nid in v["ids"]
                if await self.graph_backing.get_node(nid) is not None
            ]
        if "SELECT * FROM af_node" in s and "WHERE" not in s:
            nodes: list[dict[str, Any]] = []
            for nid in list(self.graph_backing._nodes):
                node = await self.graph_backing.get_node(nid)
                if node:
                    nodes.append(_node_record(node))
            return nodes
        if s.startswith("DELETE FROM af_node WHERE af_id = $id"):
            await self.graph_backing.delete_node(v["id"], cascade=True)
            return []

        # ---- GRAPH: af_edge ----
        if "DELETE FROM af_edge WHERE in.af_id = $src" in s and "edge_type = $edge_type" in s:
            await self.graph_backing.delete_edge(v["src"], v["dst"], edge_type=v["edge_type"])
            return []
        if "DELETE FROM af_edge WHERE in.af_id = $id OR out.af_id = $id" in s:
            # Cascade delete of all edges incident on the node — handled
            # by the subsequent DELETE FROM af_node call via cascade=True.
            return []
        if "RELATE $s->af_edge->$d" in s:
            await self.graph_backing.add_edge(
                GraphEdge(
                    src=v["src"],
                    dst=v["dst"],
                    edge_type=v["edge_type"],
                    properties=dict(v["properties"]),
                )
            )
            return []
        if "FROM af_edge" in s and ("in.af_id" in s or "out.af_id" in s):
            return await self._dispatch_edge_select(s, v)

        # ---- VECTOR ----
        if "UPSERT type::thing('af_vector', $id)" in s:
            self.vectors[v["id"]] = {
                "af_id": v["id"],
                "embedding": list(v["embedding"]),
                "text": v["text"],
                "metadata": dict(v["metadata"]),
            }
            return []
        if s == "SELECT * FROM af_vector":
            return [dict(r) for r in self.vectors.values()]
        if "SELECT af_id FROM af_vector WHERE af_id IN $ids" in s:
            return [{"af_id": nid} for nid in v["ids"] if nid in self.vectors]
        if "DELETE FROM af_vector WHERE af_id IN $ids" in s:
            for nid in v["ids"]:
                self.vectors.pop(nid, None)
            return []

        # ---- MEMORY: af_claim ----
        if "UPSERT type::thing('af_claim', $id)" in s:
            await self.memory_backing.put(
                Claim(
                    id=v["id"],
                    project=v["project"],
                    agent=v["agent"],
                    run_id=v["run_id"],
                    category=v["category"],
                    payload=json.loads(v["payload"]),
                    supersedes=v["supersedes"],
                    created_at=datetime.fromisoformat(v["created_at"]),
                )
            )
            return []
        if "SELECT * FROM af_claim WHERE af_id = $id" in s:
            cl = await self.memory_backing.get(v["id"])
            return [_claim_record(cl)] if cl else []
        if "SELECT * FROM af_claim" in s:
            return await self._dispatch_claim_select(s, v)
        if s.startswith("DELETE FROM af_claim WHERE") and "RETURN BEFORE" in s:
            older_than = v.get("older_than")
            removed = await self.memory_backing.delete(
                run_id=v.get("run_id"),
                category=v.get("category"),
                older_than=datetime.fromisoformat(older_than) if older_than else None,
            )
            # Driver counts via len(_flatten(rows)); return that many sentinel
            # records so the count matches.
            return [{"af_id": f"removed-{i}"} for i in range(removed)]

        msg = f"SurrealFakeRunner: unrecognised SurrealQL: {surrealql!r}"
        raise AssertionError(msg)

    async def close(self) -> None:
        self.closed = True

    async def _dispatch_edge_select(self, s: str, v: dict[str, Any]) -> list[dict[str, Any]]:
        # Determine direction from the WHERE clause.
        if "in.af_id = $id AND" not in s and "in.af_id = $id" in s:
            direction = "out"
        elif (
            "out.af_id = $id AND" in s
            or s.split("WHERE")[1].strip().split(" ")[0] == "out.af_id = $id"
        ):
            direction = "in"
        elif "in.af_id = $id OR out.af_id = $id" in s:
            direction = "any"
        elif "in.af_id = $id" in s:
            direction = "out"
        elif "out.af_id = $id" in s:
            direction = "in"
        else:
            direction = "any"
        # in.af_id = $src AND out.af_id = $dst — the delete_edge probe.
        if "in.af_id = $src" in s and "out.af_id = $dst" in s:
            edges = await self.graph_backing.get_edges(v["src"], direction="out")
            for e in edges:
                if e.dst == v["dst"] and e.edge_type == v["edge_type"]:
                    return [{"id": "fake-edge-id"}]
            return []
        edges = await self.graph_backing.get_edges(
            v["id"],
            edge_type=v.get("edge_type"),
            direction=direction,  # type: ignore[arg-type]
        )
        return [
            {
                "src": e.src,
                "dst": e.dst,
                "edge_type": e.edge_type,
                "properties": dict(e.properties),
            }
            for e in edges
        ]

    async def _dispatch_claim_select(self, s: str, v: dict[str, Any]) -> list[dict[str, Any]]:
        claims = await self.memory_backing.query(
            project=v.get("project"),
            agent=v.get("agent"),
            category=v.get("category"),
            run_id=v.get("run_id"),
            limit=v.get("limit", 100),
        )
        m = re.search(r"LIMIT \$limit", s)
        if m and "limit" in v:
            claims = claims[: v["limit"]]
        return [_claim_record(c) for c in claims]


def _node_record(node: GraphNode) -> dict[str, Any]:
    return {
        "af_id": node.id,
        "labels": list(node.labels),
        "properties": dict(node.properties),
    }


def _claim_record(claim: Claim) -> dict[str, Any]:
    return {
        "af_id": claim.id,
        "project": claim.project,
        "agent": claim.agent,
        "run_id": claim.run_id,
        "category": claim.category,
        "payload": json.dumps(claim.payload),
        "supersedes": claim.supersedes,
        "created_at": claim.created_at.isoformat(),
    }


@pytest.fixture
def surreal_fake_runner() -> SurrealFakeRunner:
    return SurrealFakeRunner()
