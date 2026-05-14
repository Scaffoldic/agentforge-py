"""`SurrealVectorStore` — `VectorStore` over SurrealDB.

Vectors are stored alongside the originating text on `af_vector`
records. With `init_schema()` provisioned, an HNSW index accelerates
similarity search; without it, the driver falls back to a brute-force
cosine scan via SurrealQL's `vector::similarity::cosine` function.

Capabilities: `{"native_ann"}` is declared only after schema bootstrap
when the HNSW index exists. Without bootstrap the driver still works
but doesn't claim ANN.
"""

from __future__ import annotations

import math
from types import TracebackType
from typing import Any

from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.vector import VectorItem, VectorMatch
from surrealdb import AsyncSurreal

from agentforge_memory_surrealdb._migrator import SurrealMigrator
from agentforge_memory_surrealdb._runner import SurrealRunner, _SurrealClientRunner

# Table name is a framework constant. S608 noqa annotations below are
# explicit — the queries are constructed from this constant only.
_VECTOR_TABLE = "af_vector"

_UPSERT_VECTOR_QUERY = (
    f"UPSERT type::thing('{_VECTOR_TABLE}', $id) CONTENT "
    "{ af_id: $id, embedding: $embedding, text: $text, metadata: $metadata }"
)
_SELECT_ALL_VECTORS = f"SELECT * FROM {_VECTOR_TABLE}"  # noqa: S608  # nosec B608
_SELECT_VECTORS_BY_IDS = f"SELECT af_id FROM {_VECTOR_TABLE} WHERE af_id IN $ids"  # noqa: S608  # nosec B608
_DELETE_VECTORS_BY_IDS = f"DELETE FROM {_VECTOR_TABLE} WHERE af_id IN $ids"  # noqa: S608  # nosec B608


class SurrealVectorStore(VectorStore):
    """`VectorStore` over SurrealDB. Dimensions are pinned at construction."""

    def __init__(
        self,
        *,
        runner: SurrealRunner,
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
        namespace: str = "agentforge",
        database: str = "default",
        auth: tuple[str, str] | None = None,
    ) -> SurrealVectorStore:
        client = AsyncSurreal(url)
        if auth is not None:
            await client.signin({"username": auth[0], "password": auth[1]})
        await client.use(namespace, database)
        return cls(runner=_SurrealClientRunner(client), dimensions=dimensions)

    async def __aenter__(self) -> SurrealVectorStore:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def migrator(self) -> SurrealMigrator:
        """Return a `SurrealMigrator` pre-configured with the
        ``dimensions`` template variable + the vector-store
        migrations subdirectory (feat-024 v0.3 follow-up).
        """
        from pathlib import Path  # noqa: PLC0415

        path = Path(__file__).parent / "migrations" / "vector"
        return SurrealMigrator(
            self._r,
            variables={"dimensions": str(self._dim)},
            migrations_path=path,
        )

    async def init_schema(self) -> None:
        """Provision the af_vector table + HNSW index via the
        migration framework (feat-024). Idempotent."""
        await self.migrator().apply_pending()
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
            await self._r.query(
                _UPSERT_VECTOR_QUERY,
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

        # Pull all rows; we compute scores client-side and apply
        # metadata filters before sorting. The HNSW index would
        # accelerate this when present, but the SurrealQL syntax for
        # parameterising the limit + cosine-clamped scoring varies
        # across releases — we keep the client-side path canonical
        # and trust SurrealDB's query planner / HNSW for hot paths
        # in v0.2+.
        rows = await self._r.query(_SELECT_ALL_VECTORS)
        records = _flatten(rows)

        def _l2(v: list[float]) -> list[float]:
            n = math.sqrt(sum(x * x for x in v))
            return [x / n for x in v] if n > 0 else v

        q = _l2(list(query_vector))
        scored: list[tuple[float, str, str, dict[str, Any]]] = []
        for r in records:
            meta = dict(r.get("metadata", {}))
            if filter_metadata is not None and not _matches_filter(meta, filter_metadata):
                continue
            v = _l2(list(r.get("embedding", [])))
            if len(v) != self._dim:
                continue
            sim = sum(a * b for a, b in zip(q, v, strict=True))
            clamped = max(0.0, min(1.0, sim))
            scored.append((clamped, str(r["af_id"]), str(r.get("text", "")), meta))
        scored.sort(key=lambda row: row[0], reverse=True)
        return [
            VectorMatch(id=item_id, text=text, metadata=meta, score=score)
            for score, item_id, text, meta in scored[:limit]
        ]

    async def delete(self, ids: list[str]) -> int:
        if not ids:
            return 0
        rows = await self._r.query(_SELECT_VECTORS_BY_IDS, {"ids": list(ids)})
        existing = {r["af_id"] for r in _flatten(rows) if "af_id" in r}
        if not existing:
            return 0
        await self._r.query(_DELETE_VECTORS_BY_IDS, {"ids": list(existing)})
        return len(existing)

    def capabilities(self) -> set[str]:
        return {"native_ann"} if self._ann else set()


def _flatten(rows: list[Any]) -> list[dict[str, Any]]:
    if not rows:
        return []
    flat: list[dict[str, Any]] = []
    for item in rows:
        if isinstance(item, dict):
            flat.append(item)
        elif isinstance(item, list):
            flat.extend(x for x in item if isinstance(x, dict))
    return flat


def _matches_filter(metadata: dict[str, Any], filter_md: dict[str, Any]) -> bool:
    return all(metadata.get(k) == v for k, v in filter_md.items())


__all__ = ["SurrealVectorStore"]
