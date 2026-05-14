"""`PostgresVectorStore` — `VectorStore` over Postgres + pgvector.

Vectors are stored in a `vectors` table with a typed `vector(N)`
column. With `init_schema()` provisioned, an HNSW index accelerates
similarity search via pgvector's cosine-distance operator `<=>`;
without bootstrap the driver still works (sequential cosine scan)
but doesn't claim `native_ann`.

Score conversion: pgvector's `<=>` returns cosine *distance* in
`[0, 2]` (0 = identical, 1 = orthogonal, 2 = anti-correlated).
The locked contract requires similarity in `[0, 1]` (1 = identical,
0 = orthogonal-or-anti-correlated). We compute
`GREATEST(0.0, 1.0 - (embedding <=> $1))` at the SQL boundary so
cross-driver comparisons remain meaningful.

Per ADR-0014 every code path is async (asyncpg, not psycopg).
"""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Self

import asyncpg
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.vector import VectorItem, VectorMatch

from agentforge_memory_postgres._runner import PostgresRunner, _AsyncpgPoolRunner

# Table is a framework constant; all SQL composed from it is
# parameterised via asyncpg's `$1, $2, ...` placeholders. The S608 /
# B608 noqa annotations below are explicit acknowledgements of that.
_VECTORS_TABLE = "vectors"

_UPSERT_VECTOR_SQL = (
    f"INSERT INTO {_VECTORS_TABLE} (id, embedding, text, metadata) "  # noqa: S608  # nosec B608
    "VALUES ($1, $2, $3, $4::jsonb) "
    "ON CONFLICT (id) DO UPDATE SET "
    "  embedding = EXCLUDED.embedding, "
    "  text = EXCLUDED.text, "
    "  metadata = EXCLUDED.metadata"
)
_SELECT_EXISTING_IDS = f"SELECT id FROM {_VECTORS_TABLE} WHERE id = ANY($1::text[])"  # noqa: S608  # nosec B608
_DELETE_VECTORS_BY_IDS = f"DELETE FROM {_VECTORS_TABLE} WHERE id = ANY($1::text[])"  # noqa: S608  # nosec B608
_SEARCH_VECTORS_SQL = (
    f"SELECT id, text, metadata, "  # noqa: S608  # nosec B608
    f"       GREATEST(0.0, 1.0 - (embedding <=> $1)) AS score "
    f"  FROM {_VECTORS_TABLE} "
    f" WHERE metadata @> $2::jsonb "
    f" ORDER BY embedding <=> $1 "
    f" LIMIT $3"
)
_LEXICAL_SEARCH_SQL = (
    f"WITH ranked AS ("  # noqa: S608  # nosec B608
    f"  SELECT id, text, metadata, "
    f"         ts_rank_cd(embedding_tsv, plainto_tsquery('english', $1)) AS raw "
    f"    FROM {_VECTORS_TABLE} "
    f"   WHERE embedding_tsv @@ plainto_tsquery('english', $1) "
    f"     AND metadata @> $2::jsonb "
    f"   ORDER BY raw DESC "
    f"   LIMIT $3"
    f") "
    f"SELECT id, text, metadata, "
    f"       CASE WHEN MAX(raw) OVER () > 0 "
    f"            THEN raw / MAX(raw) OVER () "
    f"            ELSE 0.0 "
    f"       END AS score "
    f"  FROM ranked "
    f" ORDER BY raw DESC"
)


def _build_init_schema_sql(dimensions: int) -> str:
    """Compose schema-bootstrap SQL. `dimensions` is validated as an
    `int` by the constructor — never a free-form string — so the
    interpolation is safe. Tagged S608 / B608 nonetheless to keep the
    lint surface honest.

    Includes the feat-022 lexical-search column (``embedding_tsv``)
    + GIN index. Upgrade from a pre-feat-022 schema: re-run
    ``init_schema()`` to gain the column + index.
    """
    return (
        "CREATE EXTENSION IF NOT EXISTS vector;"
        f"CREATE TABLE IF NOT EXISTS {_VECTORS_TABLE} ("  # nosec B608
        "    id        TEXT PRIMARY KEY,"
        f"    embedding vector({int(dimensions)}) NOT NULL,"
        "    text      TEXT NOT NULL,"
        "    metadata  JSONB NOT NULL DEFAULT '{}'::jsonb"
        ");"
        f"CREATE INDEX IF NOT EXISTS idx_{_VECTORS_TABLE}_embedding "
        f"    ON {_VECTORS_TABLE} USING hnsw (embedding vector_cosine_ops);"
        f"ALTER TABLE {_VECTORS_TABLE} "  # nosec B608
        f"    ADD COLUMN IF NOT EXISTS embedding_tsv tsvector "
        f"    GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED;"
        f"CREATE INDEX IF NOT EXISTS idx_{_VECTORS_TABLE}_tsv "
        f"    ON {_VECTORS_TABLE} USING gin (embedding_tsv);"
    )


class PostgresVectorStore(VectorStore):
    """`VectorStore` over Postgres + pgvector. Dimensions pinned at
    construction.

    Use `from_dsn(dsn, dimensions=N)` for ergonomic construction; the
    bare constructor accepts an injected `PostgresRunner` so unit tests
    can fake asyncpg without spinning up Postgres.
    """

    def __init__(
        self,
        *,
        runner: PostgresRunner,
        dimensions: int,
        ann_indexed: bool = False,
    ) -> None:
        if dimensions < 1:
            msg = f"dimensions must be >= 1, got {dimensions}"
            raise ValueError(msg)
        self._r = runner
        self._dim = dimensions
        self._ann = ann_indexed

    # ------------------------------------------------------------------
    # Construction / lifecycle
    # ------------------------------------------------------------------

    @classmethod
    async def from_dsn(
        cls,
        dsn: str,
        *,
        dimensions: int,
        min_size: int = 1,
        max_size: int = 10,
    ) -> Self:
        """Open an asyncpg pool and return a vector store with the
        pgvector codec registered on every pooled connection."""
        pool = await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)
        return cls(
            runner=_AsyncpgPoolRunner(pool, setup_pgvector=True),
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

    async def init_schema(self) -> None:
        """Provision the vectors table + HNSW index. Idempotent.

        After this returns, the store declares the `"native_ann"`
        capability — the HNSW index is in place. Skip this for
        read-only workloads or when the schema is managed externally.
        """
        await self._r.execute(_build_init_schema_sql(self._dim))
        self._ann = True

    async def close(self) -> None:
        await self._r.close()

    def dimensions(self) -> int:
        return self._dim

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
            await self._r.execute(
                _UPSERT_VECTOR_SQL,
                item.id,
                list(item.vector),
                item.text,
                json.dumps(dict(item.metadata)),
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

        # The `metadata @> $2::jsonb` predicate is conjunctive: every
        # key/value in `filter_metadata` must be present in the row's
        # JSONB. Empty filter (`{}`) matches everything.
        rows = await self._r.fetch(
            _SEARCH_VECTORS_SQL,
            list(query_vector),
            json.dumps(dict(filter_metadata or {})),
            limit,
        )
        return [
            VectorMatch(
                id=str(row["id"]),
                text=str(row["text"]),
                metadata=_ensure_dict(row["metadata"]),
                score=float(row["score"]),
            )
            for row in rows
        ]

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
        if not self._ann:
            msg = (
                "PostgresVectorStore.lexical_search requires init_schema() "
                "to have run (the embedding_tsv column + GIN index live "
                "alongside the HNSW vector index)."
            )
            raise RuntimeError(msg)
        rows = await self._r.fetch(
            _LEXICAL_SEARCH_SQL,
            query,
            json.dumps(dict(filter_metadata or {})),
            limit,
        )
        return [
            VectorMatch(
                id=str(row["id"]),
                text=str(row["text"]),
                metadata=_ensure_dict(row["metadata"]),
                score=float(row["score"]),
            )
            for row in rows
        ]

    async def delete(self, ids: list[str]) -> int:
        if not ids:
            return 0
        existing_rows = await self._r.fetch(_SELECT_EXISTING_IDS, list(ids))
        existing = {str(r["id"]) for r in existing_rows}
        if not existing:
            return 0
        await self._r.execute(_DELETE_VECTORS_BY_IDS, list(existing))
        return len(existing)

    def capabilities(self) -> set[str]:
        """`native_ann` + `hybrid_search` are both declared **only**
        after `init_schema()` provisions the HNSW + GIN indexes.
        Without bootstrap the driver still does cosine search as a
        brute-force fallback, but lexical search would fail — so the
        capability vocabulary stays honest per ADR-0009."""
        caps: set[str] = set()
        if self._ann:
            caps.add("native_ann")
            caps.add("hybrid_search")
        return caps


def _ensure_dict(value: Any) -> dict[str, Any]:
    """asyncpg returns JSONB as parsed Python objects via its codec;
    str fallback covers the (uncommon) raw-text path."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return dict(json.loads(value)) if value else {}
    return {}


__all__ = ["PostgresVectorStore"]
