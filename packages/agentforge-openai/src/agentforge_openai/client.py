"""`OpenAIClient` — `LLMClient` over OpenAI's chat.completions API.

Maps framework shapes onto OpenAI's request/response model:

- System prompt → first `{"role": "system", ...}` element in messages.
- Messages → `[{"role": ..., "content": ...}]`.
  Tool result messages encode with `role="tool"` + `tool_call_id`.
- Tools → `[{"type": "function", "function": {...}}]`.

Finish reasons normalised:
  stop / length / tool_calls / function_call / content_filter →
  end_turn / max_tokens / tool_use / tool_use / other
"""

from __future__ import annotations

import json
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

from agentforge_openai._pricing import chat_cost_usd

if TYPE_CHECKING:
    from agentforge_openai._runner import OpenAIRunner


_PROVIDER_NAME = "openai"
_DEFAULT_TIMEOUT_SECONDS = 60.0

_FINISH_REASON_MAP: dict[str, StopReason] = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "content_filter": "other",
}

_VISION_MODELS = frozenset({"gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"})


@register_provider("openai")
class OpenAIClient(LLMClient):
    """`LLMClient` over OpenAI's chat.completions API."""

    def __init__(
        self,
        *,
        model_id: str,
        runner: OpenAIRunner | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        json_mode: bool = False,
    ) -> None:
        if not model_id:
            raise ValueError("model_id must be a non-empty string")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._runner = (
            runner
            if runner is not None
            else _build_sdk_runner(
                api_key=api_key,
                base_url=base_url,
                organization=organization,
            )
        )
        self._model = model_id
        self._timeout_seconds = timeout_seconds
        self._json_mode = json_mode

    @classmethod
    def from_config(
        cls,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        json_mode: bool = False,
    ) -> OpenAIClient:  # pragma: no cover — exercised only with `-m live`.
        """Build an `OpenAIClient` backed by a real `openai.AsyncOpenAI`."""
        return cls(
            model_id=model,
            api_key=api_key,
            base_url=base_url,
            organization=organization,
            timeout_seconds=timeout_seconds,
            json_mode=json_mode,
        )

    def capabilities(self) -> set[str]:
        caps = {"tools", "json_mode", "streaming"}
        if _canonical_chat(self._model) in _VISION_MODELS:
            caps.add("vision")
        return caps

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        raw = await self._runner.chat_completions_create(
            model=self._model,
            messages=_build_messages(system, messages),
            tools=_tools_to_openai(tools),
            timeout_s=self._timeout_seconds,
            extra=self._extra_kwargs(),
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

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _extra_kwargs(self) -> dict[str, Any] | None:
        if self._json_mode:
            return {"response_format": {"type": "json_object"}}
        return None

    async def _stream_request(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None,
    ) -> AsyncIterator[StreamChunk]:
        stream = await self._runner.chat_completions_stream(
            model=self._model,
            messages=_build_messages(system, messages),
            tools=_tools_to_openai(tools),
            timeout_s=self._timeout_seconds,
            extra=self._extra_kwargs(),
        )
        tool_buffers: dict[int, dict[str, Any]] = {}
        stop_reason: StopReason = "end_turn"
        usage = TokenUsage(input_tokens=0, output_tokens=0)

        async for event in stream:
            for choice in event.get("choices", []) or []:
                delta = choice.get("delta") or {}
                text = delta.get("content")
                if text:
                    yield StreamChunk(kind="text", delta=text)
                for tc in delta.get("tool_calls") or []:
                    idx = int(tc.get("index", 0))
                    buf = tool_buffers.setdefault(
                        idx,
                        {"id": "", "name": "", "input_json": ""},
                    )
                    if tc.get("id"):
                        buf["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        buf["name"] = fn["name"]
                    if fn.get("arguments"):
                        buf["input_json"] += fn["arguments"]
                finish_raw = choice.get("finish_reason")
                if finish_raw:
                    stop_reason = _FINISH_REASON_MAP.get(finish_raw, "other")
            usage_raw = event.get("usage")
            if usage_raw:
                usage = TokenUsage(
                    input_tokens=int(usage_raw.get("prompt_tokens", 0)),
                    output_tokens=int(usage_raw.get("completion_tokens", 0)),
                )

        for buf in tool_buffers.values():
            import json as _json  # noqa: PLC0415

            try:
                args = _json.loads(buf["input_json"]) if buf["input_json"] else {}
            except _json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            yield StreamChunk(
                kind="tool_call",
                tool_call=ToolCall(id=buf["id"], name=buf["name"], arguments=args),
            )

        cost = chat_cost_usd(
            self._model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        yield StreamChunk(
            kind="stop",
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=cost,
        )

    def _normalise_response(self, raw: dict[str, Any]) -> LLMResponse:
        choices = raw.get("choices") or []
        choice0 = choices[0] if choices else {}
        msg = choice0.get("message") or {}

        content = msg.get("content") or ""
        if isinstance(content, list):
            # gpt-4o may return content as a list of parts; flatten text parts.
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )

        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            import json as _json  # noqa: PLC0415

            try:
                args = _json.loads(args_raw)
            except _json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            tool_calls.append(
                ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args)
            )

        usage_raw = raw.get("usage") or {}
        usage = TokenUsage(
            input_tokens=int(usage_raw.get("prompt_tokens", 0)),
            output_tokens=int(usage_raw.get("completion_tokens", 0)),
        )

        finish_raw = choice0.get("finish_reason") or "stop"
        stop_reason: StopReason = _FINISH_REASON_MAP.get(finish_raw, "other")

        cost = chat_cost_usd(
            self._model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )

        return LLMResponse(
            content=content,
            tool_calls=tuple(tool_calls),
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=cost,
            model=raw.get("model", self._model),
            provider=_PROVIDER_NAME,
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _build_messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
    """Build the OpenAI messages list. System prompt becomes the first
    element when non-empty."""
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})
    out.extend(_message_to_openai(m) for m in messages)
    return out


def _message_to_openai(message: Message) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id or "",
            "content": message.content,
        }
    if message.role == "system":
        # Should be hoisted by the caller; defensive passthrough.
        return {"role": "system", "content": message.content}
    if message.role == "assistant" and message.tool_calls:
        # Round-trip tool_calls so the subsequent role="tool" message
        # pairs cleanly via tool_call_id (bug-009).
        return {
            "role": "assistant",
            "content": message.content or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(dict(tc.arguments)),
                    },
                }
                for tc in message.tool_calls
            ],
        }
    return {"role": message.role, "content": message.content}


def _tools_to_openai(tools: list[ToolSpec] | None) -> list[dict[str, Any]] | None:
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


def _canonical_chat(model: str) -> str:
    for suffix_prefix in ("-2025", "-2026", "-2027", "-2028", "-2029", "-2030"):
        idx = model.find(suffix_prefix)
        if idx > 0:
            return model[:idx]
    return model


def _build_sdk_runner(  # pragma: no cover — `-m live` only.
    *,
    api_key: str | None,
    base_url: str | None,
    organization: str | None,
) -> OpenAIRunner:
    try:
        import openai  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "openai is not installed. Install via "
            "`pip install agentforge-openai[openai]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_openai._runner import _OpenAISDKRunner  # noqa: PLC0415

    kwargs: dict[str, Any] = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    if organization:
        kwargs["organization"] = organization
    client = openai.AsyncOpenAI(**kwargs)
    return _OpenAISDKRunner(client)


__all__ = ["OpenAIClient"]
