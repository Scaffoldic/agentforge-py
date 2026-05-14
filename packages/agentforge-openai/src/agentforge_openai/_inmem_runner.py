"""In-memory `OpenAIRunner` for unit tests."""

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
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class _EmbedCall:
    model: str
    inputs: list[str]
    timeout_s: float
    dimensions: int | None


def _default_chat_response() -> dict[str, Any]:
    return {
        "id": "chatcmpl_test",
        "model": "gpt-test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "stop",
            },
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _default_embedding_response(model: str, inputs: list[str], dims: int) -> dict[str, Any]:
    return {
        "model": model,
        "data": [{"index": i, "embedding": [0.0] * dims} for i in range(len(inputs))],
        "usage": {"prompt_tokens": sum(len(t) for t in inputs), "total_tokens": 0},
    }


class FakeOpenAIRunner:
    """In-memory recorder for unit tests."""

    def __init__(self) -> None:
        self._chat_response: dict[str, Any] = _default_chat_response()
        self._stream_chunks: list[dict[str, Any]] = []
        self._embedding_dims: int = 1536
        self._embedding_response: dict[str, Any] | None = None
        self.chat_calls: list[_ChatCall] = []
        self.stream_calls: list[_ChatCall] = []
        self.embedding_calls: list[_EmbedCall] = []
        self.closed = False

    def set_chat_response(self, response: dict[str, Any]) -> None:
        self._chat_response = response

    def set_stream_chunks(self, chunks: list[dict[str, Any]]) -> None:
        self._stream_chunks = list(chunks)

    def set_embedding_dims(self, dims: int) -> None:
        self._embedding_dims = dims

    def set_embedding_response(self, response: dict[str, Any]) -> None:
        self._embedding_response = response

    async def chat_completions_create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.chat_calls.append(
            _ChatCall(
                model=model,
                messages=[dict(m) for m in messages],
                tools=[dict(t) for t in tools] if tools else None,
                timeout_s=timeout_s,
                extra=dict(extra or {}),
            ),
        )
        return self._chat_response

    async def chat_completions_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        self.stream_calls.append(
            _ChatCall(
                model=model,
                messages=[dict(m) for m in messages],
                tools=[dict(t) for t in tools] if tools else None,
                timeout_s=timeout_s,
                extra=dict(extra or {}),
            ),
        )
        return _stream_iter(self._stream_chunks)

    async def embeddings_create(
        self,
        *,
        model: str,
        inputs: list[str],
        timeout_s: float,
        dimensions: int | None = None,
    ) -> dict[str, Any]:
        self.embedding_calls.append(
            _EmbedCall(
                model=model, inputs=list(inputs), timeout_s=timeout_s, dimensions=dimensions
            ),
        )
        if self._embedding_response is not None:
            return self._embedding_response
        return _default_embedding_response(model, inputs, dimensions or self._embedding_dims)

    async def close(self) -> None:
        self.closed = True


async def _stream_iter(chunks: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    for c in chunks:
        yield c


__all__ = ["FakeOpenAIRunner"]
