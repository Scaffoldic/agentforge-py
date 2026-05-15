"""In-memory `LiteLLMRunner` for unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Call:
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None
    timeout_s: float
    extra: dict[str, Any] = field(default_factory=dict)


def _default_response() -> dict[str, Any]:
    return {
        "id": "chatcmpl_test",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "stop",
            },
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


class FakeLiteLLMRunner:
    """In-memory recorder."""

    def __init__(self) -> None:
        self._response: dict[str, Any] = _default_response()
        self.calls: list[_Call] = []
        self.closed = False

    def set_response(self, response: dict[str, Any]) -> None:
        self._response = response

    async def acompletion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            _Call(
                model=model,
                messages=[dict(m) for m in messages],
                tools=[dict(t) for t in tools] if tools else None,
                timeout_s=timeout_s,
                extra=dict(extra or {}),
            ),
        )
        return self._response

    async def close(self) -> None:
        self.closed = True


__all__ = ["FakeLiteLLMRunner"]
