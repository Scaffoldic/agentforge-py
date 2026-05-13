"""Internal asyncpg-runner abstraction for the postgres chat history.

`PostgresChatHistory` always goes through one of these — never the
pool directly — so unit tests inject a `PostgresFakeRunner` that
interprets the SQL vocabulary the driver emits and routes operations
to in-memory backings. Mirrors the pattern in
`agentforge-memory-postgres/_runner.py`.
"""

from __future__ import annotations

from typing import Any, Protocol


class PostgresRunner(Protocol):  # pragma: no cover — Protocol method stubs
    """Thin slice of `asyncpg.Pool` we depend on."""

    async def fetch(self, sql: str, *params: Any) -> list[Any]: ...

    async def fetchrow(self, sql: str, *params: Any) -> Any | None: ...

    async def execute(self, sql: str, *params: Any) -> None: ...

    async def execute_returning_count(self, sql: str, *params: Any) -> int: ...

    async def close(self) -> None: ...


class _AsyncpgPoolRunner:  # pragma: no cover — exercised only with `-m live`
    """Production runner wrapping `asyncpg.Pool`."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def fetch(self, sql: str, *params: Any) -> list[Any]:
        async with self._pool.acquire() as conn:
            return list(await conn.fetch(sql, *params))

    async def fetchrow(self, sql: str, *params: Any) -> Any | None:
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, *params)

    async def execute(self, sql: str, *params: Any) -> None:
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(sql, *params)

    async def execute_returning_count(self, sql: str, *params: Any) -> int:
        async with self._pool.acquire() as conn, conn.transaction():
            tag = await conn.execute(sql, *params)
        return _parse_count(tag)

    async def close(self) -> None:
        await self._pool.close()


def _parse_count(tag: Any) -> int:  # pragma: no cover — exercised via live
    if not isinstance(tag, str):
        return 0
    parts = tag.rsplit(maxsplit=1)
    if not parts:
        return 0
    try:
        return int(parts[-1])
    except ValueError:
        return 0


__all__ = ["PostgresRunner"]
