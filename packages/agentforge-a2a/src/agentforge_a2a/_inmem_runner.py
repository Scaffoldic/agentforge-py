"""In-memory fakes implementing the A2A runner protocols (feat-014).

`FakeA2AClientRunner` lets unit + integration tests run without
spinning up an HTTP server. It records every call for later
assertion and returns scripted responses.

`FakeA2AServerRunner` is a tiny placeholder for the server-side
runner — `A2AServer.serve()` against this runner becomes a
no-op suitable for tests.

Lives in `src/` (not `tests/`) so external packages can import
the fakes for their own integration tests.
"""

from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Call:
    url: str
    headers: dict[str, str]
    json: dict[str, Any] | None
    ssl_context: ssl.SSLContext | None
    timeout_s: float


class FakeA2AClientRunner:
    """Records POSTs / GETs / streams and returns canned data."""

    def __init__(
        self,
        *,
        response: dict[str, Any] | None = None,
        get_response: dict[str, Any] | None = None,
        responses_stream: list[dict[str, Any]] | None = None,
    ) -> None:
        self._response: dict[str, Any] = response if response is not None else {}
        self._get_response: dict[str, Any] | None = get_response
        self._stream: list[dict[str, Any]] = list(responses_stream or [])
        self._error: Exception | None = None
        self.calls: list[_Call] = []
        self.get_calls: list[_Call] = []
        self.stream_calls: list[_Call] = []
        self.closed = False

    @classmethod
    def with_response(cls, response: dict[str, Any]) -> FakeA2AClientRunner:
        return cls(response=response)

    def set_response(self, response: dict[str, Any]) -> None:
        self._response = response

    def set_get_response(self, response: dict[str, Any]) -> None:
        self._get_response = response

    def set_stream(self, chunks: list[dict[str, Any]]) -> None:
        self._stream = list(chunks)

    def set_error(self, error: Exception) -> None:
        """Next `post()` (or `get()` / `post_stream()`) raises this."""
        self._error = error

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> dict[str, Any]:
        self.calls.append(
            _Call(
                url=url,
                headers=dict(headers),
                json=dict(json),
                ssl_context=ssl_context,
                timeout_s=timeout_s,
            )
        )
        if self._error is not None:
            err, self._error = self._error, None
            raise err
        return dict(self._response)

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> dict[str, Any]:
        self.get_calls.append(
            _Call(
                url=url,
                headers=dict(headers),
                json=None,
                ssl_context=ssl_context,
                timeout_s=timeout_s,
            )
        )
        if self._error is not None:
            err, self._error = self._error, None
            raise err
        body = self._get_response if self._get_response is not None else self._response
        return dict(body)

    async def post_stream(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        ssl_context: ssl.SSLContext | None,
        timeout_s: float,
    ) -> AsyncIterator[dict[str, Any]]:
        self.stream_calls.append(
            _Call(
                url=url,
                headers=dict(headers),
                json=dict(json),
                ssl_context=ssl_context,
                timeout_s=timeout_s,
            )
        )
        if self._error is not None:
            err, self._error = self._error, None
            raise err
        for chunk in self._stream:
            yield dict(chunk)

    async def close(self) -> None:
        self.closed = True


@dataclass
class FakeA2AServerRunner:
    """No-op server runner suitable for tests + the inline bridge."""

    serving: bool = False
    stop_called: bool = False
    _events: list[str] = field(default_factory=list)

    async def serve(self) -> None:
        self.serving = True
        self._events.append("serve")

    async def stop(self) -> None:
        self.serving = False
        self.stop_called = True
        self._events.append("stop")


__all__ = [
    "FakeA2AClientRunner",
    "FakeA2AServerRunner",
]
