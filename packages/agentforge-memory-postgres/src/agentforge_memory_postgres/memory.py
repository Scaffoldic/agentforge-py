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

from agentforge_memory_postgres._runner import PostgresRunner, _AsyncpgPoolRunner

# Table names are framework constants — never derived from user input.
# All SQL composed from these constants is parameterised via asyncpg's
# `$1, $2, ...` placeholders (no user input in f-strings). The S608 /
# B608 noqa annotations below are explicit acknowledgements of that
# fact, not relaxations of the lint surface.
_CLAIMS_TABLE = "claims"

_INIT_SCHEMA_SQL = (
    f"CREATE TABLE IF NOT EXISTS {_CLAIMS_TABLE} ("  # nosec B608
    "    id         TEXT PRIMARY KEY,"
    "    project    TEXT NOT NULL,"
    "    agent      TEXT NOT NULL,"
    "    run_id     TEXT NOT NULL,"
    "    category   TEXT NOT NULL,"
    "    payload    JSONB NOT NULL,"
    "    supersedes TEXT,"
    "    created_at TIMESTAMPTZ NOT NULL"
    ");"
    f"CREATE INDEX IF NOT EXISTS idx_{_CLAIMS_TABLE}_project_agent "
    f"    ON {_CLAIMS_TABLE}(project, agent);"
    f"CREATE INDEX IF NOT EXISTS idx_{_CLAIMS_TABLE}_run_id "
    f"    ON {_CLAIMS_TABLE}(run_id);"
    f"CREATE INDEX IF NOT EXISTS idx_{_CLAIMS_TABLE}_category "
    f"    ON {_CLAIMS_TABLE}(category);"
)

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

    async def init_schema(self) -> None:
        """Create the `claims` table + indices (idempotent). Opt-in.

        Skip for read-only workloads or when the schema is managed
        externally; required before first write for full correctness.
        """
        await self._r.execute(_INIT_SCHEMA_SQL)

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
