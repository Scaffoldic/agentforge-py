"""`FakeLLMClient` — minimal scripted-response `LLMClient` for unit tests.

Used by feat-002's strategy tests. Replaced by feat-016's full
`MockLLMClient` (which supports recording / replay / capability
simulation) when that lands; until then, this class is enough to
drive the four reasoning strategies through their unit and
integration tests.

Usage:

    fake = FakeLLMClient(
        responses=[
            LLMResponse(content="thought 1", stop_reason="tool_use",
                        tool_calls=(ToolCall(id="t1", name="search",
                                             arguments={"q": "x"}),),
                        usage=TokenUsage(input_tokens=10, output_tokens=5),
                        cost_usd=0.001, model="m", provider="p"),
            LLMResponse(content="final answer", stop_reason="end_turn",
                        usage=TokenUsage(input_tokens=12, output_tokens=8),
                        cost_usd=0.002, model="m", provider="p"),
        ],
    )
    # When the strategy under test calls fake.call(...) twice,
    # it gets the two scripted responses in order.

Responses can also be callables (called with the call's args) for
dynamic scripting:

    FakeLLMClient(responses=[lambda system, messages, tools=None: ...])
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.values.messages import LLMResponse, Message, TokenUsage, ToolSpec

ResponseSpec = LLMResponse | Callable[..., LLMResponse]


class FakeLLMClient(LLMClient):
    """Scripted-response `LLMClient` for tests.

    Constructor takes a list of `LLMResponse` instances OR callables
    that build a response from the call args. Each `.call()` returns
    the next item in the list; raises if the list is exhausted.
    """

    def __init__(
        self,
        responses: list[ResponseSpec] | None = None,
        *,
        capabilities: set[str] | None = None,
    ) -> None:
        self._responses: list[ResponseSpec] = list(responses or [])
        self._call_count: int = 0
        self._captured: list[tuple[str, list[Message], list[ToolSpec] | None]] = []
        self._capabilities: set[str] = set(capabilities or ())
        self._closed: bool = False

    @property
    def call_count(self) -> int:
        """Number of `.call()` invocations so far."""
        return self._call_count

    @property
    def captured(
        self,
    ) -> list[tuple[str, list[Message], list[ToolSpec] | None]]:
        """Every `(system, messages, tools)` triple seen by `.call()`,
        in order. Useful for asserting the strategy sent the expected
        messages."""
        return list(self._captured)

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        if self._closed:
            raise RuntimeError("FakeLLMClient.close() was already called")
        if self._call_count >= len(self._responses):
            raise RuntimeError(
                f"FakeLLMClient exhausted after {self._call_count} calls; "
                f"add more scripted responses or check the strategy's loop."
            )
        spec = self._responses[self._call_count]
        self._captured.append((system, list(messages), tools))
        self._call_count += 1
        if callable(spec):
            return spec(system=system, messages=messages, tools=tools)
        return spec

    async def close(self) -> None:
        self._closed = True

    def capabilities(self) -> set[str]:
        return set(self._capabilities)


def echo_response(
    *,
    content: str = "ok",
    stop_reason: str = "end_turn",
    cost_usd: float = 0.0,
    input_tokens: int = 1,
    output_tokens: int = 1,
    **_: Any,
) -> LLMResponse:
    """Convenience builder for an `LLMResponse` with sensible defaults.

    Used by tests that only care about a single LLM call's output
    shape and don't want to hand-write the full `LLMResponse`
    construction every time.
    """
    return LLMResponse(
        content=content,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        cost_usd=cost_usd,
        model="fake",
        provider="fake",
    )
