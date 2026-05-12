"""Internal A2A runner protocols (feat-014).

`A2AClientRunner` is the thin slice of httpx we depend on for
outgoing calls; `A2AServerRunner` wraps the uvicorn lifecycle
for the embedded server. Tests inject fakes so the unit suite
doesn't need a real network socket.

Production runners (`_HTTPXClientRunner`, `_UvicornServerRunner`)
are exercised by the `@pytest.mark.live` integration tests in
`tests/integration/` (feat-014 v0.2 follow-up). Their bodies
stay under ``# pragma: no cover`` because the unit suite uses
the fakes in `_inmem_runner.py`; coverage of the real transport
lives in the live job.
"""

from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import httpx
    import uvicorn
    from fastapi import FastAPI


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

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> dict[str, Any]: ...

    def post_stream(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> AsyncIterator[dict[str, Any]]: ...

    async def close(self) -> None: ...


class A2AServerRunner(Protocol):
    """Subset of `uvicorn.Server` we depend on. Tests inject a
    fake; production builds a real uvicorn server via
    `_UvicornServerRunner`."""

    async def serve(self) -> None: ...

    async def stop(self) -> None: ...


_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_SSE_DATA_PREFIX = "data: "


class _HTTPXClientRunner:  # pragma: no cover — exercised only with `-m live`
    """Production `A2AClientRunner` — wraps `httpx.AsyncClient`.

    The client is allocated lazily on the first call so
    instantiation stays cheap and the constructor stays sync.
    `close()` shuts the underlying httpx client down.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self, ssl_context: ssl.SSLContext | None) -> httpx.AsyncClient:
        if self._client is None:
            import httpx  # noqa: PLC0415

            verify: ssl.SSLContext | bool = ssl_context if ssl_context is not None else True
            self._client = httpx.AsyncClient(verify=verify)
        return self._client

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> dict[str, Any]:
        from agentforge_core.production.exceptions import (  # noqa: PLC0415
            A2AAuthError,
            A2ACallError,
        )

        client = self._ensure_client(ssl_context)
        response = await client.post(url, headers=headers, json=json, timeout=timeout_s)
        if response.status_code in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN):
            raise A2AAuthError(
                f"a2a peer rejected credentials ({response.status_code}): {response.text!r}"
            )
        if response.status_code >= 400:  # noqa: PLR2004
            raise A2ACallError(f"a2a peer returned HTTP {response.status_code}: {response.text!r}")
        parsed: dict[str, Any] = response.json()
        return parsed

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> dict[str, Any]:
        from agentforge_core.production.exceptions import (  # noqa: PLC0415
            A2AAuthError,
            A2ACallError,
        )

        client = self._ensure_client(ssl_context)
        response = await client.get(url, headers=headers, timeout=timeout_s)
        if response.status_code in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN):
            raise A2AAuthError(
                f"a2a peer rejected credentials ({response.status_code}): {response.text!r}"
            )
        if response.status_code >= 400:  # noqa: PLR2004
            raise A2ACallError(f"a2a peer returned HTTP {response.status_code}: {response.text!r}")
        parsed: dict[str, Any] = response.json()
        return parsed

    async def post_stream(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> AsyncIterator[dict[str, Any]]:
        import json as _json  # noqa: PLC0415

        from agentforge_core.production.exceptions import (  # noqa: PLC0415
            A2AAuthError,
            A2ACallError,
        )

        client = self._ensure_client(ssl_context)
        stream_headers = dict(headers)
        stream_headers.setdefault("Accept", "text/event-stream")
        async with client.stream(
            "POST", url, headers=stream_headers, json=json, timeout=timeout_s
        ) as response:
            if response.status_code in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN):
                await response.aread()
                raise A2AAuthError(
                    f"a2a peer rejected credentials ({response.status_code}): {response.text!r}"
                )
            if response.status_code >= 400:  # noqa: PLR2004
                await response.aread()
                raise A2ACallError(
                    f"a2a peer returned HTTP {response.status_code}: {response.text!r}"
                )
            async for line in response.aiter_lines():
                if not line or not line.startswith(_SSE_DATA_PREFIX):
                    continue
                payload = line[len(_SSE_DATA_PREFIX) :]
                try:
                    parsed: dict[str, Any] = _json.loads(payload)
                except _json.JSONDecodeError as exc:
                    raise A2ACallError(
                        f"a2a peer streamed an unparseable SSE frame: {payload!r}"
                    ) from exc
                yield parsed

    async def close(self) -> None:
        if self._client is None:
            return
        client, self._client = self._client, None
        await client.aclose()


class _UvicornServerRunner:  # pragma: no cover — exercised only with `-m live`
    """Production `A2AServerRunner` — wraps `uvicorn.Server`.

    `serve()` blocks until either an external signal sets
    `should_exit = True` or `stop()` is called from another
    task. `stop()` is idempotent.
    """

    def __init__(
        self,
        app: FastAPI,
        *,
        host: str = "127.0.0.1",
        port: int = 8080,
        log_level: str = "info",
    ) -> None:
        self._app = app
        self._host = host
        self._port = port
        self._log_level = log_level
        self._server: uvicorn.Server | None = None

    async def serve(self) -> None:
        import uvicorn  # noqa: PLC0415

        config = uvicorn.Config(
            self._app, host=self._host, port=self._port, log_level=self._log_level
        )
        self._server = uvicorn.Server(config)
        try:
            await self._server.serve()
        finally:
            self._server = None

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.should_exit = True


__all__ = [
    "A2AClientRunner",
    "A2AServerRunner",
]
