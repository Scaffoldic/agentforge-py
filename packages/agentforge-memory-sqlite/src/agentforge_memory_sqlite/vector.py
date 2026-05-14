"""`SqliteVectorStore` — `VectorStore` over SQLite via aiosqlite.

Vectors are stored as fixed-width BLOBs (8 bytes per float64, packed
big-endian). On search the entire table is loaded and cosine
similarity is computed in Python — O(N) per query. Fine for
~10k vectors; v0.2 will add an opt-in `sqlite-vec` extension path.

Schema is created on first connect via `CREATE TABLE IF NOT EXISTS`
and `dimensions` are pinned per database. Re-opening with a
different dimensions value raises at construction.
"""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from types import TracebackType
from typing import Any

import aiosqlite
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.values.vector import VectorItem, VectorMatch

from agentforge_memory_sqlite._migrator import SqliteMigrator


class SqliteVectorStore(VectorStore):
    """Persistent `VectorStore` backed by a SQLite file.

    Use `from_path(path, dimensions)` for ergonomic construction. The
    bare constructor accepts an opened connection plus dimensions for
    callers who manage their own connection.
    """

    def __init__(self, *, connection: aiosqlite.Connection, dimensions: int) -> None:
        if dimensions < 1:
            raise ValueError(f"dimensions must be >= 1, got {dimensions}")
        self._db = connection
        self._dim = dimensions

    @classmethod
    async def from_path(cls, path: str | Path, *, dimensions: int) -> SqliteVectorStore:
        """Open or create a vector store at `path` with `dimensions`.

        If the file already contains a vector index with a different
        dimension, raises `ValueError` — dimensions are pinned per
        database to prevent silent corruption.
        """
        if dimensions < 1:
            raise ValueError(f"dimensions must be >= 1, got {dimensions}")
        connection = await aiosqlite.connect(str(path))
        connection.row_factory = aiosqlite.Row
        # feat-024: schema bootstrap via the migration framework.
        await SqliteMigrator(connection).apply_pending()
        # Pin dimensions on first use; verify on re-open.
        async with connection.execute(
            "SELECT value FROM vector_meta WHERE key = 'dimensions'"
        ) as cur:
            existing = await cur.fetchone()
        if existing is None:
            await connection.execute(
                "INSERT INTO vector_meta(key, value) VALUES ('dimensions', ?)",
                (str(dimensions),),
            )
            await connection.commit()
        else:
            stored = int(existing["value"])
            if stored != dimensions:
                await connection.close()
                raise ValueError(
                    f"vector store at {path!s} has dimensions={stored} "
                    f"but caller asked for dimensions={dimensions}"
                )
        return cls(connection=connection, dimensions=dimensions)

    async def __aenter__(self) -> SqliteVectorStore:
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

    def migrator(self) -> SqliteMigrator:
        """Return a `SqliteMigrator` configured against the
        package's bundled migrations directory (feat-024)."""
        return SqliteMigrator(self._db)

    async def upsert(self, items: list[VectorItem]) -> None:
        rows: list[tuple[str, bytes, str, str]] = []
        for item in items:
            if len(item.vector) != self._dim:
                raise ValueError(
                    f"vector for id={item.id!r} has length {len(item.vector)} "
                    f"but store dimensions={self._dim}"
                )
            normalised = _l2_normalise(item.vector)
            rows.append(
                (
                    item.id,
                    _pack_vector(normalised),
                    item.text,
                    json.dumps(item.metadata),
                )
            )
        await self._db.executemany(
            "INSERT OR REPLACE INTO vectors(id, vector, text, metadata) VALUES (?, ?, ?, ?)",
            rows,
        )
        await self._db.commit()

    async def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        if len(query_vector) != self._dim:
            raise ValueError(
                f"query vector has length {len(query_vector)} but store dimensions={self._dim}"
            )

        query = _l2_normalise(query_vector)
        scored: list[tuple[float, str, str, dict[str, Any]]] = []
        async with self._db.execute("SELECT * FROM vectors") as cur:
            async for row in cur:
                metadata = json.loads(row["metadata"])
                if filter_metadata is not None and not _matches_filter(metadata, filter_metadata):
                    continue
                vec = _unpack_vector(row["vector"], self._dim)
                similarity = sum(a * b for a, b in zip(query, vec, strict=True))
                clamped = max(0.0, min(1.0, similarity))
                scored.append((clamped, row["id"], row["text"], metadata))

        scored.sort(key=lambda r: r[0], reverse=True)
        return [
            VectorMatch(id=item_id, text=text, metadata=meta, score=score)
            for score, item_id, text, meta in scored[:limit]
        ]

    async def lexical_search(
        self,
        query: str,
        *,
        limit: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        escaped = _escape_fts_query(query)
        if not escaped:
            return []
        # Over-fetch when metadata filter is set so post-filter has
        # room to work; the in-memory store uses the same pattern.
        over_fetch = limit if filter_metadata is None else limit * 4
        async with self._db.execute(
            "SELECT v.id, v.text, v.metadata, "
            "       -bm25(vectors_fts) AS raw "
            "  FROM vectors_fts "
            "  JOIN vectors v ON v.rowid = vectors_fts.rowid "
            " WHERE vectors_fts MATCH ? "
            " ORDER BY raw DESC "
            " LIMIT ?",
            (escaped, max(over_fetch, 1)),
        ) as cur:
            rows = list(await cur.fetchall())
        if not rows:
            return []

        top_raw = float(rows[0]["raw"])
        matches: list[VectorMatch] = []
        for row in rows:
            metadata = json.loads(row["metadata"])
            if filter_metadata is not None and not _matches_filter(metadata, filter_metadata):
                continue
            raw = float(row["raw"])
            score = raw / top_raw if top_raw > 0 else 0.0
            matches.append(
                VectorMatch(
                    id=str(row["id"]),
                    text=str(row["text"]),
                    metadata=metadata,
                    score=score,
                )
            )
            if len(matches) >= limit:
                break
        return matches

    def capabilities(self) -> set[str]:
        """SQLite ships native FTS5; hybrid_search is always available
        once the schema is set up in `from_path()`."""
        return {"hybrid_search"}

    async def delete(self, ids: list[str]) -> int:
        if not ids:
            return 0
        # `placeholders` is a string of `?` characters, never user
        # input — `tuple(ids)` is the parametrised payload.
        placeholders = ",".join("?" for _ in ids)
        sql = f"DELETE FROM vectors WHERE id IN ({placeholders})"  # noqa: S608  # nosec B608
        async with self._db.execute(sql, tuple(ids)) as cur:
            removed = cur.rowcount
        await self._db.commit()
        # rowcount is -1 when undefined; coerce to 0 for safety.
        return max(0, removed)

    async def close(self) -> None:
        await self._db.close()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _pack_vector(vector: tuple[float, ...]) -> bytes:
    """Pack a float tuple into a fixed-width float64 BLOB."""
    return struct.pack(f"<{len(vector)}d", *vector)


def _unpack_vector(blob: bytes, dim: int) -> tuple[float, ...]:
    """Reverse of `_pack_vector`."""
    return struct.unpack(f"<{dim}d", blob)


def _l2_normalise(vector: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return vector
    return tuple(x / norm for x in vector)


def _matches_filter(metadata: dict[str, Any], filter_md: dict[str, Any]) -> bool:
    return all(metadata.get(k) == v for k, v in filter_md.items())


def _escape_fts_query(query: str) -> str:
    """Wrap every term in double-quotes so user input that contains
    FTS5 special syntax (``AND`` / ``OR`` / ``*`` / parens / colons)
    is treated literally. Empty input yields an empty string."""
    terms = ['"' + term.replace('"', '""') + '"' for term in query.split() if term]
    return " ".join(terms)


__all__ = ["SqliteVectorStore"]
