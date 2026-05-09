"""Shared fixtures for agentforge-bedrock tests.

The unit tests never hit AWS — they inject a `_FakeBedrockClient` into
the `BedrockClient` via the `session=` constructor kwarg.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest


class _FakeBedrockClient:
    """Stand-in for the aioboto3 `bedrock-runtime` client.

    Records every Converse / ConverseStream call and returns scripted
    responses. Tests set `responses` (for converse) or
    `stream_responses` (for converse_stream) to a list of dicts /
    callables / event lists; each call pops the next item.
    """

    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses: list[Any] = list(responses or [])
        self.stream_responses: list[Any] = []
        self.calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []
        self.exceptions: list[Exception | None] = []

    async def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("FakeBedrockClient: no scripted response left")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(**kwargs)
        return item

    async def converse_stream(self, **kwargs: Any) -> dict[str, Any]:
        self.stream_calls.append(kwargs)
        if not self.stream_responses:
            raise AssertionError("FakeBedrockClient: no scripted stream response left")
        item = self.stream_responses.pop(0)
        if isinstance(item, Exception):
            raise item
        # Items can be a list of events (auto-wrapped into an iterator
        # under the "stream" key), or a dict already shaped like a
        # ConverseStream response.
        if isinstance(item, list):
            return {"stream": _async_iter(item)}
        return item


async def _async_iter(items: list[Any]) -> AsyncIterator[Any]:
    """Minimal async-iterable wrapper for a list of stream events."""
    for it in items:
        yield it


class _FakeSession:
    """Stand-in for `aioboto3.Session` — its `.client(...)` returns an
    async-context-manager wrapping our `_FakeBedrockClient`."""

    def __init__(self, fake_client: _FakeBedrockClient) -> None:
        self._fake_client = fake_client

    def client(self, _service: str, **_kwargs: Any) -> Any:
        @asynccontextmanager
        async def _cm() -> AsyncIterator[_FakeBedrockClient]:
            yield self._fake_client

        return _cm()


@pytest.fixture
def fake_bedrock() -> _FakeBedrockClient:
    return _FakeBedrockClient()


@pytest.fixture
def fake_session(fake_bedrock: _FakeBedrockClient) -> _FakeSession:
    return _FakeSession(fake_bedrock)


def converse_response(
    *,
    text: str = "ok",
    stop_reason: str = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 5,
    tool_use: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal Bedrock Converse response dict."""
    blocks: list[dict[str, Any]] = []
    if text:
        blocks.append({"text": text})
    if tool_use is not None:
        blocks.append({"toolUse": tool_use})
    return {
        "output": {"message": {"role": "assistant", "content": blocks}},
        "stopReason": stop_reason,
        "usage": {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": input_tokens + output_tokens,
        },
    }
