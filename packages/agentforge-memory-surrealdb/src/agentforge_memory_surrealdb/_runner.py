"""Internal SurrealQL-runner abstraction.

Every store wraps a `SurrealRunner` — production wraps `AsyncSurreal`
from the official `surrealdb` SDK; unit tests inject a fake that
interprets the SurrealQL vocabulary the drivers emit and routes to
in-memory backings.

Per ADR-0014 every code path is async — uses `surrealdb.AsyncSurreal`,
not the sync client.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Protocol


class SurrealRunner(Protocol):
    """Internal protocol — every SurrealQL query goes through here."""

    async def query(self, surrealql: str, vars: dict[str, Any] | None = None) -> list[Any]:
        """Run a SurrealQL statement and return its result rows."""

    async def close(self) -> None:
        """Release the underlying SurrealDB connection."""


class _SurrealClientRunner:
    """Production runner — wraps `surrealdb.AsyncSurreal`."""

    def __init__(self, client: Any) -> None:
        # `client` is `surrealdb.AsyncSurreal`; typed as Any because
        # the surrealdb package ships without py.typed and the
        # workspace mypy override strips its types.
        self._client = client

    async def query(self, surrealql: str, vars: dict[str, Any] | None = None) -> list[Any]:
        result = await self._client.query(surrealql, vars or {})
        # SurrealDB returns the result list directly in v1.x.
        return list(result) if result is not None else []

    async def close(self) -> None:
        # AsyncSurreal exposes either `close()` or async-context-manager;
        # we always have a constructed instance so call close directly.
        await self._client.close()


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


__all__ = ["SurrealRunner"]
