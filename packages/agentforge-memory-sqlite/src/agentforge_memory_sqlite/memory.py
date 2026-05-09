"""`SqliteMemoryStore` — `MemoryStore` over SQLite via aiosqlite.

Single-table schema: every claim is stored as one row keyed by `id`
with project / agent / category / run_id / supersedes columns and
the JSON payload as a TEXT blob. Queries hit composite indices on
the common filter combinations.

Schema is created on first connect via `CREATE TABLE IF NOT EXISTS`.
No migrations in v0.1 — the table shape is fixed.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any

import aiosqlite
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.claim import Claim

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS claims (
    id          TEXT PRIMARY KEY,
    project     TEXT NOT NULL,
    agent       TEXT NOT NULL,
    run_id      TEXT NOT NULL,
    category    TEXT NOT NULL,
    payload     TEXT NOT NULL,
    supersedes  TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_project_agent
    ON claims(project, agent);
CREATE INDEX IF NOT EXISTS idx_claims_run_id
    ON claims(run_id);
CREATE INDEX IF NOT EXISTS idx_claims_category
    ON claims(category);
"""


class SqliteMemoryStore(MemoryStore):
    """Persistent `MemoryStore` backed by a single SQLite file.

    Use `from_path(path)` for ergonomic construction; the bare
    constructor accepts an already-opened `aiosqlite.Connection` for
    callers who manage the connection themselves.
    """

    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self._db = connection

    # ------------------------------------------------------------------
    # Construction / lifecycle
    # ------------------------------------------------------------------

    @classmethod
    async def from_path(cls, path: str | Path) -> SqliteMemoryStore:
        """Open or create a SQLite database at `path` and return a store.

        `path` may be `":memory:"` for an ephemeral in-process database,
        or a filesystem path (the parent directory must exist).
        """
        connection = await aiosqlite.connect(str(path))
        connection.row_factory = aiosqlite.Row
        await connection.executescript(_SCHEMA_SQL)
        await connection.commit()
        return cls(connection=connection)

    async def __aenter__(self) -> SqliteMemoryStore:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._db.close()

    # ------------------------------------------------------------------
    # MemoryStore contract
    # ------------------------------------------------------------------

    async def put(self, claim: Claim) -> str:
        await self._db.execute(
            """INSERT OR REPLACE INTO claims
               (id, project, agent, run_id, category, payload, supersedes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                claim.id,
                claim.project,
                claim.agent,
                claim.run_id,
                claim.category,
                json.dumps(claim.payload),
                claim.supersedes,
                claim.created_at.isoformat(),
            ),
        )
        await self._db.commit()
        return claim.id

    async def get(self, claim_id: str) -> Claim | None:
        async with self._db.execute(
            "SELECT * FROM claims WHERE id = ?",
            (claim_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return _row_to_claim(row)

    async def query(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[Claim]:
        sql, params = _build_filter_sql(project, agent, category, run_id, limit)
        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [_row_to_claim(row) for row in rows]

    async def supersede(self, old_id: str, new_claim: Claim) -> str:
        existing = await self.get(old_id)
        if existing is None:
            raise ModuleError(f"Cannot supersede unknown claim id: {old_id!r}")
        if new_claim.supersedes is None:
            new_claim = new_claim.model_copy(update={"supersedes": old_id})
        elif new_claim.supersedes != old_id:
            raise ModuleError(
                f"new_claim.supersedes={new_claim.supersedes!r} does not match old_id={old_id!r}"
            )
        return await self.put(new_claim)

    def stream(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
    ) -> AsyncIterator[Claim]:
        sql, params = _build_filter_sql(project, agent, category, run_id, limit=None)

        async def _agen() -> AsyncIterator[Claim]:
            async with self._db.execute(sql, params) as cur:
                async for row in cur:
                    yield _row_to_claim(row)

        return _agen()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _row_to_claim(row: Any) -> Claim:
    """Convert an `aiosqlite.Row` into a `Claim`."""
    return Claim(
        id=row["id"],
        project=row["project"],
        agent=row["agent"],
        run_id=row["run_id"],
        category=row["category"],
        payload=json.loads(row["payload"]),
        supersedes=row["supersedes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _build_filter_sql(
    project: str | None,
    agent: str | None,
    category: str | None,
    run_id: str | None,
    limit: int | None,
) -> tuple[str, tuple[Any, ...]]:
    """Compose a SELECT with conjunctive filters and an optional LIMIT."""
    where: list[str] = []
    params: list[Any] = []
    if project is not None:
        where.append("project = ?")
        params.append(project)
    if agent is not None:
        where.append("agent = ?")
        params.append(agent)
    if category is not None:
        where.append("category = ?")
        params.append(category)
    if run_id is not None:
        where.append("run_id = ?")
        params.append(run_id)

    sql = "SELECT * FROM claims"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return sql, tuple(params)


__all__ = ["SqliteMemoryStore"]
