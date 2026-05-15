"""In-memory `AnthropicRunner` for unit tests.

Records every `messages_create` / `messages_stream` call's args
and returns a scripted response shape mirroring the Anthropic
Messages API.

The default scripted response is a single text block with
`stop_reason="end_turn"` and zero usage; tests override via
`set_response` / `set_stream_events`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _CreateCall:
    model: str
    system: str | None
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None
    max_tokens: int
    timeout_s: float
    extra: dict[str, Any] = field(default_factory=dict)


def _default_response() -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-test",
        "content": [{"type": "text", "text": ""}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }


class _FakeStreamContext:
    """Async context manager mimicking the Anthropic SDK's stream
    object. `events` yields the scripted event sequence."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events

    async def __aenter__(self) -> _FakeStreamContext:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        async def _gen() -> AsyncIterator[dict[str, Any]]:
            for ev in self._events:
                yield ev

        return _gen()


class FakeAnthropicRunner:
    """In-memory recorder for unit tests."""

    def __init__(self) -> None:
        self._response: dict[str, Any] = _default_response()
        self._stream_events: list[dict[str, Any]] = []
        self.create_calls: list[_CreateCall] = []
        self.stream_calls: list[_CreateCall] = []
        self.closed = False

    def set_response(self, response: dict[str, Any]) -> None:
        """Replace the dict returned by subsequent `messages_create`
        calls."""
        self._response = response

    def set_stream_events(self, events: list[dict[str, Any]]) -> None:
        """Replace the event list yielded by subsequent
        `messages_stream` contexts."""
        self._stream_events = list(events)

    async def messages_create(
        self,
        *,
        model: str,
        system: str | None,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.create_calls.append(
            _CreateCall(
                model=model,
                system=system,
                messages=[dict(m) for m in messages],
                tools=[dict(t) for t in tools] if tools else None,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                extra=dict(extra or {}),
            ),
        )
        return self._response

    async def messages_stream(
        self,
        *,
        model: str,
        system: str | None,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> _FakeStreamContext:
        self.stream_calls.append(
            _CreateCall(
                model=model,
                system=system,
                messages=[dict(m) for m in messages],
                tools=[dict(t) for t in tools] if tools else None,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                extra=dict(extra or {}),
            ),
        )
        return _FakeStreamContext(self._stream_events)

    async def close(self) -> None:
        self.closed = True


__all__ = ["FakeAnthropicRunner"]
