"""`PostgresMemoryStore` — `MemoryStore` over Postgres via asyncpg.

Single-table schema: every claim is one row keyed by `id` with
project / agent / category / run_id / supersedes columns and a JSONB
payload. Queries hit composite indices on the common filter
combinations.

`init_schema()` creates the table + indices via
`CREATE TABLE IF NOT EXISTS`. Idempotent. No migration framework —
the schema shape is pinned for v0.1; a future delta lands alongside
schema-migrations support.

Per ADR-0014 every code path is async (asyncpg, not psycopg).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from types import TracebackType
from typing import Any, Self

import asyncpg
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.claim import Claim

from agentforge_memory_postgres._migrator import PostgresMigrator
from agentforge_memory_postgres._runner import PostgresRunner, _AsyncpgPoolRunner

# Table names are framework constants — never derived from user input.
# All SQL composed from these constants is parameterised via asyncpg's
# `$1, $2, ...` placeholders (no user input in f-strings). The S608 /
# B608 noqa annotations below are explicit acknowledgements of that
# fact, not relaxations of the lint surface.
_CLAIMS_TABLE = "claims"

_UPSERT_CLAIM_SQL = (
    f"INSERT INTO {_CLAIMS_TABLE} "  # noqa: S608  # nosec B608
    "(id, project, agent, run_id, category, payload, supersedes, created_at) "
    "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8) "
    "ON CONFLICT (id) DO UPDATE SET "
    "  project = EXCLUDED.project, agent = EXCLUDED.agent, "
    "  run_id = EXCLUDED.run_id, category = EXCLUDED.category, "
    "  payload = EXCLUDED.payload, supersedes = EXCLUDED.supersedes, "
    "  created_at = EXCLUDED.created_at"
)
_SELECT_CLAIM_BY_ID = f"SELECT * FROM {_CLAIMS_TABLE} WHERE id = $1"  # noqa: S608  # nosec B608


class PostgresMemoryStore(MemoryStore):
    """Persistent `MemoryStore` backed by Postgres.

    Use `from_dsn(dsn)` for ergonomic construction; the bare
    constructor accepts an injected `PostgresRunner` so unit tests can
    fake asyncpg without spinning up Postgres.
    """

    def __init__(self, *, runner: PostgresRunner) -> None:
        self._r = runner

    # ------------------------------------------------------------------
    # Construction / lifecycle
    # ------------------------------------------------------------------

    @classmethod
    async def from_dsn(
        cls,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
    ) -> Self:
        """Open an asyncpg pool against `dsn` and return a store."""
        pool = await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)
        return cls(runner=_AsyncpgPoolRunner(pool))

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def migrator(self) -> PostgresMigrator:
        """Return a `PostgresMigrator` configured against the
        package's bundled migrations directory (feat-024)."""
        return PostgresMigrator(self._r)

    async def init_schema(self) -> None:
        """Apply every bundled migration (idempotent). Opt-in.

        Delegates to the feat-024 migration framework — schema
        provisioning is now versioned + checksum-tracked. Older
        deployments that previously called this method continue to
        work; subsequent calls only apply pending migrations.

        Skip for read-only workloads or when the schema is managed
        externally; required before first write for full correctness.
        """
        await self.migrator().apply_pending()

    async def close(self) -> None:
        await self._r.close()

    # ------------------------------------------------------------------
    # MemoryStore contract
    # ------------------------------------------------------------------

    async def put(self, claim: Claim) -> str:
        await self._r.execute(
            _UPSERT_CLAIM_SQL,
            claim.id,
            claim.project,
            claim.agent,
            claim.run_id,
            claim.category,
            json.dumps(claim.payload),
            claim.supersedes,
            claim.created_at,
        )
        return claim.id

    async def get(self, claim_id: str) -> Claim | None:
        row = await self._r.fetchrow(_SELECT_CLAIM_BY_ID, claim_id)
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
        sql, params = _build_filter_sql(
            project=project,
            agent=agent,
            category=category,
            run_id=run_id,
            limit=limit,
        )
        rows = await self._r.fetch(sql, *params)
        return [_row_to_claim(r) for r in rows]

    async def supersede(self, old_id: str, new_claim: Claim) -> str:
        existing = await self.get(old_id)
        if existing is None:
            msg = f"Cannot supersede unknown claim id: {old_id!r}"
            raise ModuleError(msg)
        if new_claim.supersedes is None:
            new_claim = new_claim.model_copy(update={"supersedes": old_id})
        elif new_claim.supersedes != old_id:
            msg = f"new_claim.supersedes={new_claim.supersedes!r} does not match old_id={old_id!r}"
            raise ModuleError(msg)
        return await self.put(new_claim)

    def stream(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
    ) -> AsyncIterator[Claim]:
        sql, params = _build_filter_sql(
            project=project,
            agent=agent,
            category=category,
            run_id=run_id,
            limit=None,
        )

        async def _agen() -> AsyncIterator[Claim]:
            rows = await self._r.fetch(sql, *params)
            for r in rows:
                yield _row_to_claim(r)

        return _agen()

    async def delete(
        self,
        *,
        run_id: str | None = None,
        older_than: datetime | None = None,
        category: str | None = None,
    ) -> int:
        if run_id is None and older_than is None and category is None:
            msg = "delete() requires at least one filter; refusing to wipe every claim."
            raise ModuleError(msg)
        where: list[str] = []
        params: list[Any] = []
        next_idx = 1
        if run_id is not None:
            where.append(f"run_id = ${next_idx}")
            params.append(run_id)
            next_idx += 1
        if category is not None:
            where.append(f"category = ${next_idx}")
            params.append(category)
            next_idx += 1
        if older_than is not None:
            where.append(f"created_at < ${next_idx}")
            params.append(older_than)
            next_idx += 1
        sql = f"DELETE FROM {_CLAIMS_TABLE} WHERE " + " AND ".join(  # noqa: S608  # nosec B608
            where,
        )
        return await self._r.execute_returning_count(sql, *params)

    def capabilities(self) -> set[str]:
        return {"transactions"}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _row_to_claim(row: Any) -> Claim:
    """Convert an asyncpg row (dict-like) into a `Claim`.

    asyncpg returns `Record` objects which support `row["col"]`. JSONB
    payloads come back already-parsed when the column is declared
    `jsonb`; for the dict-codec edge case we fall back to
    `json.loads`.
    """
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    created = row["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    return Claim(
        id=row["id"],
        project=row["project"],
        agent=row["agent"],
        run_id=row["run_id"],
        category=row["category"],
        payload=payload,
        supersedes=row["supersedes"],
        created_at=created,
    )


def _build_filter_sql(
    *,
    project: str | None,
    agent: str | None,
    category: str | None,
    run_id: str | None,
    limit: int | None,
) -> tuple[str, tuple[Any, ...]]:
    """Compose a SELECT with conjunctive filters and an optional LIMIT.

    Emits asyncpg's `$1, $2, ...` placeholders (numbered positionally,
    not the `?` aiosqlite uses).
    """
    where: list[str] = []
    params: list[Any] = []
    next_idx = 1

    def _add(column: str, value: Any) -> None:
        nonlocal next_idx
        where.append(f"{column} = ${next_idx}")
        params.append(value)
        next_idx += 1

    if project is not None:
        _add("project", project)
    if agent is not None:
        _add("agent", agent)
    if category is not None:
        _add("category", category)
    if run_id is not None:
        _add("run_id", run_id)

    sql = f"SELECT * FROM {_CLAIMS_TABLE}"  # noqa: S608  # nosec B608
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at"
    if limit is not None:
        sql += f" LIMIT ${next_idx}"
        params.append(limit)
    return sql, tuple(params)


__all__ = ["PostgresMemoryStore"]
