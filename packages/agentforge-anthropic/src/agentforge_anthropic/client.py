"""`AnthropicClient` — `LLMClient` over Anthropic's native Messages API.

Maps framework shapes onto Anthropic's request/response model:

- System prompt → top-level `system=` string (Anthropic separates
  system from messages, unlike OpenAI).
- Messages → `[{"role": "user"|"assistant", "content": [...]}]`
  Tool result messages encode as user-role content blocks with
  `{"type": "tool_result", "tool_use_id": ..., "content": ...}`.
- Tools → `[{"name": ..., "description": ..., "input_schema": ...}]`.

Stop reasons are normalised:
  end_turn / stop_sequence / tool_use / max_tokens → mirror provider
  refusal → "other"
"""

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

from agentforge_anthropic._pricing import compute_cost_usd

if TYPE_CHECKING:
    from agentforge_anthropic._runner import AnthropicRunner


_PROVIDER_NAME = "anthropic"
_DEFAULT_MAX_TOKENS = 4096
_DEFAULT_TIMEOUT_SECONDS = 60.0

_STOP_REASON_MAP: dict[str, StopReason] = {
    "end_turn": "end_turn",
    "stop_sequence": "stop_sequence",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "refusal": "other",
}


@register_provider("anthropic")
class AnthropicClient(LLMClient):
    """`LLMClient` over Anthropic's native Messages API.

    Construction:

    - `AnthropicClient(runner=<AnthropicRunner>, model=...)` —
      direct injection (tests).
    - `AnthropicClient.from_config(model=..., api_key=..., ...)` —
      builds the production runner by lazy-importing
      `anthropic.AsyncAnthropic`.
    """

    def __init__(
        self,
        *,
        model_id: str,
        runner: AnthropicRunner | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not model_id:
            raise ValueError("model_id must be a non-empty string")
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._runner = (
            runner
            if runner is not None
            else _build_sdk_runner(
                api_key=api_key,
                base_url=base_url,
            )
        )
        self._model = model_id
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds

    @classmethod
    def from_config(
        cls,
        *,
        model: str,
        api_key: str | None = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        base_url: str | None = None,
    ) -> AnthropicClient:  # pragma: no cover — exercised only with `-m live`.
        """Build an `AnthropicClient` backed by a real
        `anthropic.AsyncAnthropic` client. Convenience helper — the
        constructor with `runner=None` does the same thing."""
        return cls(
            model_id=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )

    def capabilities(self) -> set[str]:
        """Native Anthropic supports tools, JSON mode (via prompt),
        prompt caching, extended thinking, and streaming."""
        return {"tools", "json_mode", "caching", "thinking", "streaming"}

    # ------------------------------------------------------------------
    # LLMClient.call (+ optional capability variants)
    # ------------------------------------------------------------------

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        raw = await self._runner.messages_create(
            model=self._model,
            system=system or None,
            messages=[_message_to_anthropic(m) for m in messages],
            tools=_tools_to_anthropic(tools),
            max_tokens=self._max_tokens,
            timeout_s=self._timeout_seconds,
            extra=None,
        )
        return self._normalise_response(raw)

    async def call_with_cache(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        cache_breakpoints: list[int],
    ) -> LLMResponse:
        """Same as `call`, but marks the content block at each indexed
        message with `cache_control: {"type": "ephemeral"}`. Anthropic
        applies caching to everything preceding each cache breakpoint.

        Anthropic requires the prefix preceding a cache point to meet a
        per-model minimum (currently 1024 tokens for Sonnet/Opus, 2048
        for Haiku). Smaller prefixes are silently un-cached. The
        response surfaces cache reads/writes via
        `usage.cache_read_input_tokens` and
        `usage.cache_creation_input_tokens`.
        """
        anth_msgs = [_message_to_anthropic(m) for m in messages]
        _inject_cache_breakpoints(anth_msgs, cache_breakpoints)
        raw = await self._runner.messages_create(
            model=self._model,
            system=system or None,
            messages=anth_msgs,
            tools=_tools_to_anthropic(tools),
            max_tokens=self._max_tokens,
            timeout_s=self._timeout_seconds,
            extra=None,
        )
        return self._normalise_response(raw)

    async def call_with_thinking(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        thinking_budget_tokens: int,
    ) -> LLMResponse:
        """Same as `call`, but enables extended thinking via
        `thinking={"type": "enabled", "budget_tokens": ...}`.

        `thinking_budget_tokens` caps the model's internal reasoning
        budget. Anthropic surfaces reasoning as `thinking` content
        blocks in the response; we strip them from `LLMResponse.content`
        (the public answer) so callers continue to see only the
        assistant's final text. `usage.thinking_tokens` reports actual
        usage.
        """
        if thinking_budget_tokens < 1:
            raise ValueError("thinking_budget_tokens must be >= 1")
        # max_tokens must be > thinking_budget_tokens per Anthropic spec.
        max_tokens = max(self._max_tokens, thinking_budget_tokens + 1024)
        raw = await self._runner.messages_create(
            model=self._model,
            system=system or None,
            messages=[_message_to_anthropic(m) for m in messages],
            tools=_tools_to_anthropic(tools),
            max_tokens=max_tokens,
            timeout_s=self._timeout_seconds,
            extra={"thinking": {"type": "enabled", "budget_tokens": thinking_budget_tokens}},
        )
        return self._normalise_response(raw)

    def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream the model's response via Anthropic's
        `messages.stream()`. Returns an async iterator that yields
        `StreamChunk`s and terminates with exactly one `kind="stop"`
        chunk carrying final usage and cost.
        """
        return self._stream_request(
            system=system,
            messages=messages,
            tools=tools,
        )

    async def close(self) -> None:
        await self._runner.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _stream_request(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None,
    ) -> AsyncIterator[StreamChunk]:
        ctx = await self._runner.messages_stream(
            model=self._model,
            system=system or None,
            messages=[_message_to_anthropic(m) for m in messages],
            tools=_tools_to_anthropic(tools),
            max_tokens=self._max_tokens,
            timeout_s=self._timeout_seconds,
            extra=None,
        )
        tool_buffers: dict[int, dict[str, Any]] = {}
        stop_reason: StopReason = "end_turn"
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        model = self._model

        async with ctx as stream:
            async for event in stream:
                chunk, new_stop, new_usage = _process_stream_event(event, tool_buffers)
                if new_stop is not None:
                    stop_reason = new_stop
                if new_usage is not None:
                    usage = new_usage
                if chunk is not None:
                    yield chunk

        cost = compute_cost_usd(
            model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
        )
        yield StreamChunk(
            kind="stop",
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=cost,
        )

    def _normalise_response(self, raw: dict[str, Any]) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in raw.get("content", []) or []:
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input") or {},
                    ),
                )
            # `thinking` blocks are dropped from the public answer.

        usage_raw = raw.get("usage", {}) or {}
        usage = TokenUsage(
            input_tokens=int(usage_raw.get("input_tokens", 0)),
            output_tokens=int(usage_raw.get("output_tokens", 0)),
            cache_read_tokens=int(usage_raw.get("cache_read_input_tokens", 0)),
            cache_write_tokens=int(usage_raw.get("cache_creation_input_tokens", 0)),
        )

        stop_reason: StopReason = _STOP_REASON_MAP.get(
            raw.get("stop_reason") or "end_turn",
            "other",
        )

        cost = compute_cost_usd(
            self._model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
        )

        return LLMResponse(
            content="".join(text_parts),
            tool_calls=tuple(tool_calls),
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=cost,
            model=raw.get("model", self._model),
            provider=_PROVIDER_NAME,
        )


# ----------------------------------------------------------------------
# Helpers — request build / streaming event normalisation
# ----------------------------------------------------------------------


def _message_to_anthropic(message: Message) -> dict[str, Any]:
    """Translate one framework `Message` into an Anthropic content block."""
    if message.role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id or "",
                    "content": message.content,
                },
            ],
        }
    if message.role == "system":
        # Should be hoisted by the caller; defensive fallback.
        return {"role": "user", "content": message.content}
    if message.role == "assistant" and message.tool_calls:
        # Round-trip tool_calls into Anthropic tool_use content blocks so
        # the next iteration's tool_result pairs by id (bug-009).
        blocks: list[dict[str, Any]] = []
        if message.content:
            blocks.append({"type": "text", "text": message.content})
        blocks.extend(
            {
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": dict(tc.arguments),
            }
            for tc in message.tool_calls
        )
        return {"role": "assistant", "content": blocks}
    return {"role": message.role, "content": message.content}


def _tools_to_anthropic(tools: list[ToolSpec] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.schema_,
        }
        for t in tools
    ]


def _inject_cache_breakpoints(
    anth_messages: list[dict[str, Any]],
    breakpoints: list[int],
) -> None:
    """Wrap each indexed message's content with a content-block
    list ending in `cache_control: {"type": "ephemeral"}`.

    Indices outside `[0, len(messages))` are dropped. Duplicates are
    ignored. Anthropic supports up to four cache breakpoints per
    request; exceeding that surfaces as a 400 from the API.
    """
    seen: set[int] = set()
    n = len(anth_messages)
    for idx in breakpoints:
        if idx in seen or not 0 <= idx < n:
            continue
        seen.add(idx)
        msg = anth_messages[idx]
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"},
                },
            ]
        elif isinstance(content, list) and content:
            last = content[-1]
            if isinstance(last, dict):
                last["cache_control"] = {"type": "ephemeral"}


def _process_stream_event(  # noqa: PLR0911 — single dispatch over event types
    event: Any,
    tool_buffers: dict[int, dict[str, Any]],
) -> tuple[StreamChunk | None, StopReason | None, TokenUsage | None]:
    """Translate one Anthropic stream event into `(chunk, stop, usage)`.

    Returns `(None, None, None)` for bookkeeping-only events. The
    Anthropic SDK emits events as Pydantic models OR plain dicts
    depending on version; we accept both via `_field()`.
    """
    et = _field(event, "type")
    if et == "content_block_start":
        block = _field(event, "content_block") or {}
        idx = int(_field(event, "index") or 0)
        if _field(block, "type") == "tool_use":
            tool_buffers[idx] = {
                "id": _field(block, "id") or "",
                "name": _field(block, "name") or "",
                "input_json": "",
            }
        return None, None, None
    if et == "content_block_delta":
        delta = _field(event, "delta") or {}
        idx = int(_field(event, "index") or 0)
        dt = _field(delta, "type")
        if dt == "text_delta":
            return StreamChunk(kind="text", delta=_field(delta, "text") or ""), None, None
        if dt == "thinking_delta":
            text = _field(delta, "thinking") or ""
            return (StreamChunk(kind="thinking", delta=text) if text else None), None, None
        if dt == "input_json_delta":
            buffered = tool_buffers.get(idx)
            if buffered is not None:
                buffered["input_json"] += _field(delta, "partial_json") or ""
        return None, None, None
    if et == "content_block_stop":
        idx = int(_field(event, "index") or 0)
        buffered = tool_buffers.pop(idx, None)
        if buffered is None:
            return None, None, None
        import json as _json  # local to keep top-level deps minimal  # noqa: PLC0415

        try:
            args = _json.loads(buffered["input_json"]) if buffered["input_json"] else {}
        except _json.JSONDecodeError:
            args = {}
        if not isinstance(args, dict):
            args = {}
        return (
            StreamChunk(
                kind="tool_call",
                tool_call=ToolCall(id=buffered["id"], name=buffered["name"], arguments=args),
            ),
            None,
            None,
        )
    if et == "message_delta":
        delta = _field(event, "delta") or {}
        stop_raw = _field(delta, "stop_reason")
        usage_raw = _field(event, "usage") or {}
        stop = _STOP_REASON_MAP.get(stop_raw) if stop_raw else None
        usage = (
            TokenUsage(
                input_tokens=int(_field(usage_raw, "input_tokens") or 0),
                output_tokens=int(_field(usage_raw, "output_tokens") or 0),
                cache_read_tokens=int(_field(usage_raw, "cache_read_input_tokens") or 0),
                cache_write_tokens=int(_field(usage_raw, "cache_creation_input_tokens") or 0),
            )
            if usage_raw
            else None
        )
        return None, stop, usage
    return None, None, None


def _field(obj: Any, name: str) -> Any:
    """Read `name` from `obj` whether it's a dict or pydantic model."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _build_sdk_runner(  # pragma: no cover — `-m live` only.
    *,
    api_key: str | None,
    base_url: str | None,
) -> AnthropicRunner:
    """Lazy-import `anthropic` and build the production runner."""
    try:
        import anthropic  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "anthropic is not installed. Install via "
            "`pip install agentforge-anthropic[anthropic]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_anthropic._runner import _AnthropicSDKRunner  # noqa: PLC0415

    kwargs: dict[str, Any] = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    client = anthropic.AsyncAnthropic(**kwargs)
    return _AnthropicSDKRunner(client)


__all__ = ["AnthropicClient"]
