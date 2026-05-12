"""Internal A2A runner protocols (feat-014).

`A2AClientRunner` is the thin slice of httpx we depend on for
outgoing calls; `A2AServerRunner` wraps the uvicorn lifecycle
for the embedded server. Tests inject fakes so the unit suite
doesn't need a real network socket.

Production runners (`_HTTPXClientRunner`, `_UvicornServerRunner`)
are scaffolded behind ``# pragma: no cover`` until the
framework's first live A2A integration test lands. The contract
surface is fully covered by the fake runners in
`_inmem_runner.py`.
"""

from __future__ import annotations

import ssl
from typing import Any, Protocol


class A2AClientRunner(Protocol):
    """Subset of `httpx.AsyncClient` we depend on for outgoing
    A2A calls. Tests inject a fake; production builds a real
    `httpx.AsyncClient` via `_HTTPXClientRunner`."""

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> dict[str, Any]: ...

    async def close(self) -> None: ...


class A2AServerRunner(Protocol):
    """Subset of `uvicorn.Server` we depend on. Tests inject a
    fake; production builds a real uvicorn server via
    `_UvicornServerRunner`."""

    async def serve(self) -> None: ...

    async def stop(self) -> None: ...


class _HTTPXClientRunner:
    """Production `A2AClientRunner` — wraps `httpx.AsyncClient`.

    Pragma-no-cover until the first live A2A integration test
    lands. Unit tests inject `FakeA2AClientRunner` from
    `_inmem_runner.py`.
    """

    def __init__(self) -> None:  # pragma: no cover — live transport
        raise NotImplementedError(
            "Production A2A runner not implemented yet. Inject a "
            "FakeA2AClientRunner in tests, or wait for the live "
            "integration scaffolding (feat-014 v0.4.1 follow-up)."
        )

    async def post(  # pragma: no cover
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover
        raise NotImplementedError


class _UvicornServerRunner:
    """Production `A2AServerRunner` — wraps `uvicorn.Server`.

    Pragma-no-cover until live integration tests land.
    """

    def __init__(self) -> None:  # pragma: no cover — live transport
        raise NotImplementedError(
            "Production A2A server runner not implemented yet. Inject "
            "FakeA2AServerRunner in tests, or wait for the live "
            "integration scaffolding (feat-014 v0.4.1 follow-up)."
        )

    async def serve(self) -> None:  # pragma: no cover
        raise NotImplementedError

    async def stop(self) -> None:  # pragma: no cover
        raise NotImplementedError


__all__ = [
    "A2AClientRunner",
    "A2AServerRunner",
]
