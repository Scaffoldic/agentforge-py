"""In-memory `OllamaRunner` for unit tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _ChatCall:
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None
    timeout_s: float
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class _EmbedCall:
    model: str
    inputs: list[str]
    timeout_s: float


def _default_chat_response() -> dict[str, Any]:
    return {
        "model": "test",
        "message": {"role": "assistant", "content": ""},
        "done_reason": "stop",
        "done": True,
        "prompt_eval_count": 0,
        "eval_count": 0,
    }


class FakeOllamaRunner:
    """In-memory recorder."""

    def __init__(self, dim: int = 1024) -> None:
        self._chat_response: dict[str, Any] = _default_chat_response()
        self._stream_events: list[dict[str, Any]] = []
        self._embedding_dim = dim
        self._embedding_response: dict[str, Any] | None = None
        self.chat_calls: list[_ChatCall] = []
        self.stream_calls: list[_ChatCall] = []
        self.embedding_calls: list[_EmbedCall] = []
        self.closed = False

    def set_chat_response(self, response: dict[str, Any]) -> None:
        self._chat_response = response

    def set_stream_events(self, events: list[dict[str, Any]]) -> None:
        self._stream_events = list(events)

    def set_embedding_dim(self, dim: int) -> None:
        self._embedding_dim = dim

    def set_embedding_response(self, response: dict[str, Any]) -> None:
        self._embedding_response = response

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.chat_calls.append(
            _ChatCall(
                model=model,
                messages=[dict(m) for m in messages],
                tools=[dict(t) for t in tools] if tools else None,
                timeout_s=timeout_s,
                options=dict(options or {}),
            ),
        )
        return self._chat_response

    def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        self.stream_calls.append(
            _ChatCall(
                model=model,
                messages=[dict(m) for m in messages],
                tools=[dict(t) for t in tools] if tools else None,
                timeout_s=timeout_s,
                options=dict(options or {}),
            ),
        )
        return _yield(self._stream_events)

    async def embed(
        self,
        *,
        model: str,
        inputs: list[str],
        timeout_s: float,
    ) -> dict[str, Any]:
        self.embedding_calls.append(
            _EmbedCall(model=model, inputs=list(inputs), timeout_s=timeout_s),
        )
        if self._embedding_response is not None:
            return self._embedding_response
        return {
            "model": model,
            "embeddings": [[0.0] * self._embedding_dim for _ in inputs],
            "prompt_eval_count": sum(len(t) for t in inputs),
        }

    async def close(self) -> None:
        self.closed = True


async def _yield(events: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for e in events:
        yield e


__all__ = ["FakeOllamaRunner"]
