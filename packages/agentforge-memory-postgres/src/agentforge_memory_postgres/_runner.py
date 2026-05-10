"""Internal asyncpg-runner abstraction.

Production stores wrap an `asyncpg.Pool`; unit tests inject a
`PostgresFakeRunner` that interprets the SQL vocabulary the drivers
emit and routes operations to in-memory backings. Every `*Store` in
this package goes through the runner — never the pool directly — so
the test boundary is a single interface.

Per ADR-0014 every code path is async. Callers must `await close()`
at shutdown to release the pool's pooled connections.
"""

from __future__ import annotations

from typing import Any, Protocol

from pgvector.asyncpg import register_vector


class PostgresRunner(Protocol):
    """Internal protocol — every SQL statement goes through one of these.

    Mirrors a thin slice of `asyncpg.Connection` / `asyncpg.Pool`:

      - `fetch` returns a list of rows (`asyncpg.Record`-like)
      - `fetchrow` returns a single row or None
      - `execute` runs a statement that doesn't return rows
      - `executemany` runs a statement with a list of parameter tuples
      - `close` releases the pool

    The vector store also needs a `register_vector(conn)` hook on
    each pooled connection so pgvector's codec is set up; the
    production runner handles that on acquisition.
    """

    async def fetch(self, sql: str, *params: Any) -> list[Any]: ...

    async def fetchrow(self, sql: str, *params: Any) -> Any | None: ...

    async def execute(self, sql: str, *params: Any) -> None: ...

    async def executemany(self, sql: str, args: list[tuple[Any, ...]]) -> None: ...

    async def close(self) -> None: ...


class _AsyncpgPoolRunner:
    """Production runner — wraps an `asyncpg.Pool`.

    Each call acquires a connection from the pool, runs the
    statement, and releases. Mutating calls (`execute`,
    `executemany`) wrap in an `async with conn.transaction():` block
    so a failed statement doesn't leave partial state.

    `setup_pgvector` should be True when this runner serves a
    `PostgresVectorStore`, so each pooled connection registers the
    pgvector codec on first acquisition.
    """

    def __init__(self, pool: Any, *, setup_pgvector: bool = False) -> None:
        # `pool` is `asyncpg.Pool`; typed as Any because asyncpg ships
        # without py.typed and the workspace mypy override strips its
        # types.
        self._pool = pool
        self._setup_pgvector = setup_pgvector

    async def fetch(self, sql: str, *params: Any) -> list[Any]:
        async with self._pool.acquire() as conn:
            await self._maybe_register_vector(conn)
            return list(await conn.fetch(sql, *params))

    async def fetchrow(self, sql: str, *params: Any) -> Any | None:
        async with self._pool.acquire() as conn:
            await self._maybe_register_vector(conn)
            return await conn.fetchrow(sql, *params)

    async def execute(self, sql: str, *params: Any) -> None:
        async with self._pool.acquire() as conn:
            await self._maybe_register_vector(conn)
            async with conn.transaction():
                await conn.execute(sql, *params)

    async def executemany(self, sql: str, args: list[tuple[Any, ...]]) -> None:
        async with self._pool.acquire() as conn:
            await self._maybe_register_vector(conn)
            async with conn.transaction():
                await conn.executemany(sql, args)

    async def close(self) -> None:
        await self._pool.close()

    async def _maybe_register_vector(self, conn: Any) -> None:
        """Register the pgvector codec on this connection (idempotent).

        pgvector ships an asyncpg helper that teaches the codec how
        to encode `list[float]` as the `vector` type and decode it
        back. We call it lazily on first use of each pooled
        connection — asyncpg caches type codecs per-connection so
        this is cheap on subsequent calls.
        """
        if not self._setup_pgvector:
            return
        await register_vector(conn)


__all__ = ["PostgresRunner"]
