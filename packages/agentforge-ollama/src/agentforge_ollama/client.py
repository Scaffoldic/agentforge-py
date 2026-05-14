"""`OllamaClient` — `LLMClient` over a local Ollama daemon."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import register_provider
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    StopReason,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolSpec,
)

if TYPE_CHECKING:
    from agentforge_ollama._runner import OllamaRunner


_PROVIDER_NAME = "ollama"
_DEFAULT_TIMEOUT_SECONDS = 120.0

_STOP_REASON_MAP: dict[str, StopReason] = {
    "stop": "end_turn",
    "length": "max_tokens",
    "load": "other",
    "tool_calls": "tool_use",
}


@register_provider("ollama")
class OllamaClient(LLMClient):
    """`LLMClient` over a local Ollama daemon."""

    def __init__(
        self,
        *,
        model_id: str,
        runner: OllamaRunner | None = None,
        host: str | None = None,
        supports_tools: bool = True,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        options: dict[str, Any] | None = None,
    ) -> None:
        if not model_id:
            raise ValueError("model_id must be a non-empty string")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._runner = runner if runner is not None else _build_sdk_runner(host=host)
        self._model = model_id
        self._supports_tools = supports_tools
        self._timeout_seconds = timeout_seconds
        self._options = dict(options) if options else None

    @classmethod
    def from_config(
        cls,
        *,
        model: str,
        host: str | None = None,
        supports_tools: bool = True,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        options: dict[str, Any] | None = None,
    ) -> OllamaClient:  # pragma: no cover — `-m live` only.
        return cls(
            model_id=model,
            host=host,
            supports_tools=supports_tools,
            timeout_seconds=timeout_seconds,
            options=options,
        )

    def capabilities(self) -> set[str]:
        caps = {"streaming"}
        if self._supports_tools:
            caps.add("tools")
        return caps

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        raw = await self._runner.chat(
            model=self._model,
            messages=_build_messages(system, messages),
            tools=_tools_to_ollama(tools) if self._supports_tools else None,
            timeout_s=self._timeout_seconds,
            options=self._options,
        )
        return self._normalise_response(raw)

    def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        return self._stream_request(system=system, messages=messages, tools=tools)

    async def close(self) -> None:
        await self._runner.close()

    async def _stream_request(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None,
    ) -> AsyncIterator[StreamChunk]:
        stream = self._runner.stream(
            model=self._model,
            messages=_build_messages(system, messages),
            tools=_tools_to_ollama(tools) if self._supports_tools else None,
            timeout_s=self._timeout_seconds,
            options=self._options,
        )
        stop_reason: StopReason = "end_turn"
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        tool_calls_seen: list[ToolCall] = []
        async for event in stream:
            msg = event.get("message") or {}
            content = msg.get("content")
            if content:
                yield StreamChunk(kind="text", delta=content)
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                tool_calls_seen.append(
                    ToolCall(
                        id=str(tc.get("id") or f"toolu_{len(tool_calls_seen)}"),
                        name=fn.get("name", ""),
                        arguments=fn.get("arguments") or {},
                    ),
                )
            if event.get("done"):
                done_reason = event.get("done_reason") or "stop"
                stop_reason = _STOP_REASON_MAP.get(done_reason, "other")
                usage = TokenUsage(
                    input_tokens=int(event.get("prompt_eval_count", 0) or 0),
                    output_tokens=int(event.get("eval_count", 0) or 0),
                )

        for tc in tool_calls_seen:
            yield StreamChunk(kind="tool_call", tool_call=tc)

        yield StreamChunk(
            kind="stop",
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=0.0,  # local inference — no cost.
        )

    def _normalise_response(self, raw: dict[str, Any]) -> LLMResponse:
        msg = raw.get("message") or {}
        content = msg.get("content") or ""
        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args_raw = fn.get("arguments") or {}
            args = args_raw if isinstance(args_raw, dict) else {}
            tool_calls.append(
                ToolCall(
                    id=str(tc.get("id") or f"toolu_{len(tool_calls)}"),
                    name=fn.get("name", ""),
                    arguments=args,
                ),
            )

        usage = TokenUsage(
            input_tokens=int(raw.get("prompt_eval_count", 0) or 0),
            output_tokens=int(raw.get("eval_count", 0) or 0),
        )

        done_reason = raw.get("done_reason") or "stop"
        stop_reason: StopReason = _STOP_REASON_MAP.get(done_reason, "other")
        if tool_calls and stop_reason == "end_turn":
            stop_reason = "tool_use"

        return LLMResponse(
            content=content,
            tool_calls=tuple(tool_calls),
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=0.0,  # local inference is free.
            model=raw.get("model", self._model),
            provider=_PROVIDER_NAME,
        )


def _build_messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        if m.role == "tool":
            out.append(
                {"role": "tool", "tool_call_id": m.tool_call_id or "", "content": m.content},
            )
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def _tools_to_ollama(tools: list[ToolSpec] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.schema_,
            },
        }
        for t in tools
    ]


def _build_sdk_runner(*, host: str | None) -> OllamaRunner:  # pragma: no cover — `-m live` only.
    try:
        import ollama  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "ollama is not installed. Install via "
            "`pip install agentforge-ollama[ollama]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_ollama._runner import _OllamaSDKRunner  # noqa: PLC0415

    client = ollama.AsyncClient(host=host) if host else ollama.AsyncClient()
    return _OllamaSDKRunner(client)


__all__ = ["OllamaClient"]
