"""Internal Cypher-runner abstraction.

Production stores wrap a real `neo4j.AsyncDriver`; unit tests inject a
`FakeRunner` that records queries and returns canned results. Every
`*Store` in this package goes through the runner — never the driver
directly — so the test boundary is a single interface.

Per ADR-0014 every code path is async — uses the neo4j AsyncDriver.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Protocol


class CypherRunner(Protocol):
    """Internal protocol — every Cypher query goes through one of these.

    Read and write are kept distinct so callers signal their intent
    (Neo4j routes reads to read replicas in a cluster setup; the fake
    runner used in tests is allowed to ignore the distinction).
    """

    async def execute_read(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Run a read-only Cypher and return all rows as dicts."""

    async def execute_write(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Run a write Cypher (committed on success) and return rows."""

    async def close(self) -> None:
        """Release the underlying driver's connection pool."""


class _Neo4jDriverRunner:
    """Production runner — wraps `neo4j.AsyncDriver`."""

    def __init__(self, driver: Any, database: str) -> None:
        # `driver` is `neo4j.AsyncDriver`; typed as Any because the
        # neo4j package ships without py.typed and the workspace mypy
        # override strips its types.
        self._driver = driver
        self._database = database

    async def execute_read(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        async with self._driver.session(database=self._database) as session:
            return list(await session.execute_read(_run_and_collect, cypher, params))

    async def execute_write(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        async with self._driver.session(database=self._database) as session:
            return list(await session.execute_write(_run_and_collect, cypher, params))

    async def close(self) -> None:
        await self._driver.close()


async def _run_and_collect(tx: Any, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Transaction work-fn: run query, materialise to dicts."""
    result = await tx.run(cypher, **params)
    return [dict(record) async for record in result]


class _AsyncCloseable(Protocol):
    """Async context-manager helper — every store implements this."""

    async def close(self) -> None: ...

    async def __aenter__(self) -> Any: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


__all__ = ["CypherRunner"]
