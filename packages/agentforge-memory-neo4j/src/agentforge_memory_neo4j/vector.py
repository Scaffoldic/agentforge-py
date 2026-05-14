"""`Neo4jVectorStore` — `VectorStore` over Neo4j 5.13+ native vector
+ fulltext indexes.

Adds the missing third ABC implementation alongside the existing
`Neo4jMemoryStore` (claims) and `Neo4jGraphStore` (knowledge
graph). Vectors are stored on `:AfVector` nodes with `af_id` /
`embedding` / `text` / `metadata` properties. A `VECTOR INDEX`
accelerates cosine-similarity search; a `FULLTEXT INDEX` powers
the `lexical_search` method used by feat-022 hybrid retrieval.

Both indexes are provisioned via the feat-024 migration framework
— see `migrations/vector/0100_vectors.cypher` for the DDL.
`init_schema()` runs `apply_pending` then flips the `_ann` flag
so `capabilities()` declares `{"native_ann", "hybrid_search"}`.

Per ADR-0014 every code path is async (Neo4j async driver).
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any, Self

from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.vector import VectorItem, VectorMatch
from neo4j import AsyncGraphDatabase

from agentforge_memory_neo4j._migrator import Neo4jMigrator
from agentforge_memory_neo4j._runner import CypherRunner, _Neo4jDriverRunner

_VECTOR_LABEL = "AfVector"
_VECTOR_INDEX = "af_vector_embedding"
_FULLTEXT_INDEX = "af_vector_text"

_UPSERT_CYPHER = (
    f"MERGE (n:{_VECTOR_LABEL} {{af_id: $id}}) "
    "SET n.embedding = $embedding, n.text = $text, n.metadata = $metadata"
)
_DELETE_PROBE_CYPHER = f"MATCH (n:{_VECTOR_LABEL}) WHERE n.af_id IN $ids RETURN n.af_id AS id"
_DELETE_CYPHER = f"MATCH (n:{_VECTOR_LABEL}) WHERE n.af_id IN $ids DETACH DELETE n"
_SEARCH_CYPHER = (
    f"CALL db.index.vector.queryNodes('{_VECTOR_INDEX}', $limit, $query) "
    "YIELD node, score "
    "RETURN node.af_id AS id, node.text AS text, "
    "node.metadata AS metadata, score AS score"
)
_LEXICAL_CYPHER = (
    f"CALL db.index.fulltext.queryNodes('{_FULLTEXT_INDEX}', $query) "
    "YIELD node, score "
    "RETURN node.af_id AS id, node.text AS text, "
    "node.metadata AS metadata, score AS raw "
    "LIMIT $limit"
)


def _vector_migrations_path() -> Path:
    return Path(__file__).parent / "migrations" / "vector"


class Neo4jVectorStore(VectorStore):
    """`VectorStore` over Neo4j 5.13+ native vector + fulltext indexes.

    Use `from_url(url, dimensions=N, auth=...)` for ergonomic
    construction; the bare constructor accepts an injected
    `CypherRunner` so unit tests can fake the driver without
    spinning up Neo4j.
    """

    def __init__(
        self,
        *,
        runner: CypherRunner,
        dimensions: int,
        ann_indexed: bool = False,
    ) -> None:
        if dimensions < 1:
            msg = f"dimensions must be >= 1, got {dimensions}"
            raise ValueError(msg)
        self._r = runner
        self._dim = dimensions
        self._ann = ann_indexed

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        dimensions: int,
        auth: tuple[str, str],
        database: str = "neo4j",
    ) -> Self:
        """Open a Neo4j connection and return a vector store."""
        driver = AsyncGraphDatabase.driver(url, auth=auth)
        return cls(
            runner=_Neo4jDriverRunner(driver, database),
            dimensions=dimensions,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def dimensions(self) -> int:
        return self._dim

    def migrator(self) -> Neo4jMigrator:
        """Return a `Neo4jMigrator` pre-configured with the
        ``dimensions`` template variable + the vector-store
        migrations subdirectory (feat-024 v0.3 follow-up)."""
        return Neo4jMigrator(
            self._r,
            variables={"dimensions": str(self._dim)},
            migrations_path=_vector_migrations_path(),
        )

    async def init_schema(self) -> None:
        """Provision the vector + fulltext + uniqueness indexes via
        the migration framework. After this returns, the store
        declares ``{"native_ann", "hybrid_search"}``."""
        await self.migrator().apply_pending()
        self._ann = True

    async def close(self) -> None:
        await self._r.close()

    # ------------------------------------------------------------------
    # VectorStore contract
    # ------------------------------------------------------------------

    async def upsert(self, items: list[VectorItem]) -> None:
        for item in items:
            if len(item.vector) != self._dim:
                msg = (
                    f"vector for id={item.id!r} has length {len(item.vector)} "
                    f"but store dimensions={self._dim}"
                )
                raise ValueError(msg)
            await self._r.execute_write(
                _UPSERT_CYPHER,
                {
                    "id": item.id,
                    "embedding": list(item.vector),
                    "text": item.text,
                    "metadata": dict(item.metadata),
                },
            )

    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        if limit < 1:
            msg = f"limit must be >= 1, got {limit}"
            raise ValueError(msg)
        if len(query_vector) != self._dim:
            msg = f"query vector has length {len(query_vector)} but store dimensions={self._dim}"
            raise ValueError(msg)

        over_fetch = limit if filter_metadata is None else limit * 4
        rows = await self._r.execute_read(
            _SEARCH_CYPHER,
            {"limit": max(over_fetch, 1), "query": list(query_vector)},
        )
        matches: list[VectorMatch] = []
        for row in rows:
            metadata = _ensure_dict(row.get("metadata"))
            if filter_metadata is not None and not _matches_filter(metadata, filter_metadata):
                continue
            score = max(0.0, min(1.0, float(row["score"])))
            matches.append(
                VectorMatch(
                    id=str(row["id"]),
                    text=str(row.get("text", "")),
                    metadata=metadata,
                    score=score,
                )
            )
            if len(matches) >= limit:
                break
        return matches

    async def lexical_search(
        self,
        query: str,
        *,
        limit: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        if limit < 1:
            msg = f"limit must be >= 1, got {limit}"
            raise ValueError(msg)
        if not query.strip():
            return []
        over_fetch = limit if filter_metadata is None else limit * 4
        rows = await self._r.execute_read(
            _LEXICAL_CYPHER,
            {"query": query, "limit": max(over_fetch, 1)},
        )
        if not rows:
            return []
        # Lucene fulltext scores are unbounded ≥ 0; max-normalise per
        # result set so the driver returns [0, 1] (matches the
        # in-memory + SQLite + SurrealDB conventions).
        top_raw = max((float(row["raw"]) for row in rows), default=0.0)
        matches: list[VectorMatch] = []
        for row in rows:
            metadata = _ensure_dict(row.get("metadata"))
            if filter_metadata is not None and not _matches_filter(metadata, filter_metadata):
                continue
            raw = float(row["raw"])
            score = raw / top_raw if top_raw > 0 else 0.0
            matches.append(
                VectorMatch(
                    id=str(row["id"]),
                    text=str(row.get("text", "")),
                    metadata=metadata,
                    score=score,
                )
            )
            if len(matches) >= limit:
                break
        return matches

    async def delete(self, ids: list[str]) -> int:
        if not ids:
            return 0
        rows = await self._r.execute_read(_DELETE_PROBE_CYPHER, {"ids": list(ids)})
        existing = {str(r["id"]) for r in rows}
        if not existing:
            return 0
        await self._r.execute_write(_DELETE_CYPHER, {"ids": list(existing)})
        return len(existing)

    def capabilities(self) -> set[str]:
        """`native_ann` + `hybrid_search` are declared only after
        `init_schema()` provisions the vector + fulltext indexes."""
        caps: set[str] = set()
        if self._ann:
            caps.add("native_ann")
            caps.add("hybrid_search")
        return caps


def _ensure_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _matches_filter(metadata: dict[str, Any], filter_md: dict[str, Any]) -> bool:
    return all(metadata.get(k) == v for k, v in filter_md.items())


__all__ = ["Neo4jVectorStore"]
