"""`BedrockClient` — `LLMClient` over AWS Bedrock Converse API.

The driver normalises Bedrock's request/response shapes into the
framework's provider-agnostic `Message` / `LLMResponse` shapes:

  - System prompt → `system=[{"text": <str>}]`
  - Messages → `[{"role": "user"|"assistant", "content": [{"text": <str>}]}]`
    Tool result messages get `content=[{"toolResult": {...}}]`.
  - Tools → `toolConfig={"tools": [{"toolSpec": {...}}]}`

The response's `output.message.content[]` is a list of blocks; we
concatenate text blocks into `LLMResponse.content` and surface
toolUse blocks as `LLMResponse.tool_calls`.

`stop_reason` is normalised:
  end_turn, tool_use, max_tokens, stop_sequence → mirror provider
  guardrail_intervened → "other" (treated as finish)

Cross-region inference profile IDs (`us.`, `eu.`, `apac.`, `global.`)
are passed through unchanged to Bedrock; the price lookup strips the
prefix transparently.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any, cast

import aioboto3
from agentforge_core.contracts.llm import LLMClient
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
from botocore.exceptions import ClientError

from agentforge_bedrock._errors import map_client_error, map_unexpected
from agentforge_bedrock._pricing import compute_cost_usd
from agentforge_bedrock._retry import with_retry

log = logging.getLogger(__name__)

_PROVIDER_NAME = "bedrock"
_DEFAULT_REGION = "us-east-1"
_DEFAULT_TIMEOUT_SECONDS = 60.0
_DEFAULT_MAX_RETRIES = 3

# Bedrock stop-reason strings -> our StopReason literal.
_STOP_REASON_MAP: dict[str, StopReason] = {
    "end_turn": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "stop_sequence": "stop_sequence",
    "guardrail_intervened": "other",
    "content_filtered": "other",
}


@register_provider("bedrock")
class BedrockClient(LLMClient):
    """`LLMClient` over AWS Bedrock Converse.

    Args:
        model_id: Bedrock model identifier — region-pinned
            (`anthropic.claude-...`), geo cross-region
            (`us.anthropic.claude-...`), or global cross-region
            (`global.anthropic.claude-sonnet-4-...`). Passed through
            to Bedrock unchanged.
        region: AWS region for the source request. Cross-region
            inference profiles handle destination routing themselves.
            Defaults to `AWS_REGION` env var, then `us-east-1`.
        max_retries: Maximum retries on retryable errors
            (RateLimitError, ServiceError, TimeoutError). Default 3.
        timeout_seconds: Per-request timeout. Default 60s.
        aws_profile: Optional named profile from `~/.aws/credentials`.
            `None` uses the default boto3 credential chain.
        session: Optional injected `aioboto3.Session` — primarily for
            tests; production code passes nothing.
    """

    def __init__(
        self,
        *,
        model_id: str,
        region: str | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        aws_profile: str | None = None,
        session: Any | None = None,
    ) -> None:
        if not model_id:
            raise ValueError("model_id must be a non-empty string")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._model_id = model_id
        self._region = region or os.environ.get("AWS_REGION") or _DEFAULT_REGION
        self._max_retries = max_retries
        self._timeout_seconds = timeout_seconds
        self._aws_profile = aws_profile
        self._session: Any | None = session
        self._client_cm: Any | None = None
        self._client: Any | None = None

    # ------------------------------------------------------------------
    # Capability declaration
    # ------------------------------------------------------------------

    def capabilities(self) -> set[str]:
        """Bedrock's Converse API supports tools, JSON mode (via prompt),
        prompt caching (cachePoint blocks), Anthropic extended thinking
        (additionalModelRequestFields.thinking), and streaming
        (ConverseStream)."""
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
        """Issue a Bedrock Converse request and normalise the response."""
        request = self._build_converse_request(system, messages, tools)
        return await self._invoke_request(request)

    async def call_with_cache(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        cache_breakpoints: list[int],
    ) -> LLMResponse:
        """Same as `call`, but inserts a Bedrock cachePoint block after
        the content of each indexed message in `messages`.

        Bedrock requires the prefix preceding a cache point to meet a
        per-model minimum (1024 tokens for current Anthropic Claude
        models). Smaller prefixes are silently un-cached. The response
        surfaces cache reads/writes via `usage.cache_read_tokens` and
        `usage.cache_write_tokens`.
        """
        request = self._build_converse_request(system, messages, tools)
        _inject_cache_points(request, cache_breakpoints)
        return await self._invoke_request(request)

    async def call_with_thinking(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        thinking_budget_tokens: int,
    ) -> LLMResponse:
        """Same as `call`, but enables Anthropic extended thinking via
        Bedrock's `additionalModelRequestFields.thinking`.

        `thinking_budget_tokens` caps the model's internal reasoning
        budget. Bedrock surfaces reasoning as `reasoningContent` blocks
        in the response; we strip them from `LLMResponse.content` (the
        public answer) so callers continue to see only the assistant's
        final text. A future feature may surface the reasoning blocks
        on a dedicated field.
        """
        if thinking_budget_tokens < 1:
            raise ValueError("thinking_budget_tokens must be >= 1")
        request = self._build_converse_request(system, messages, tools)
        request.setdefault("additionalModelRequestFields", {})["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_budget_tokens,
        }
        return await self._invoke_request(request)

    def stream(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream the model's response via Bedrock's ConverseStream.

        Returns an async iterator that yields `StreamChunk`s and
        terminates with exactly one `kind="stop"` chunk carrying final
        usage and cost.

        The contract is sync-returns-iterator (not `async def`) so
        callers don't need an extra `await` to get the iterator —
        consistent with `LLMClient.stream`'s default-raise signature.

        Note: streaming is NOT wrapped in the retry helper. A stream
        that fails mid-flight cannot be safely retried (partial output
        already consumed); the caller can wrap whole-stream invocations
        in retry logic if they want at-most-once-by-stream semantics.
        """
        request = self._build_converse_request(system, messages, tools)
        return self._stream_request(request)

    async def close(self) -> None:
        """Release the aioboto3 client + session."""
        if self._client_cm is not None:
            try:
                await self._client_cm.__aexit__(None, None, None)
            finally:
                self._client_cm = None
                self._client = None

    # ------------------------------------------------------------------
    # Internal — request build / response normalise
    # ------------------------------------------------------------------

    async def _invoke_request(self, request: dict[str, Any]) -> LLMResponse:
        """Send a built Bedrock request through retry + error-mapping,
        then normalise to `LLMResponse`. Shared by `call`,
        `call_with_cache`, and `call_with_thinking`."""
        client = await self._ensure_client()

        async def _do() -> dict[str, Any]:
            try:
                return cast(
                    "dict[str, Any]",
                    await asyncio.wait_for(
                        client.converse(**request),
                        timeout=self._timeout_seconds,
                    ),
                )
            except TimeoutError as exc:
                raise map_unexpected(exc) from exc
            except ClientError as exc:
                raise map_client_error(exc) from exc
            except Exception as exc:
                raise map_unexpected(exc) from exc

        response = await with_retry(_do, max_retries=self._max_retries)
        return self._normalise_response(response)

    async def _stream_request(self, request: dict[str, Any]) -> AsyncIterator[StreamChunk]:
        """Async generator backing `stream()`. Opens ConverseStream,
        normalises each event into a `StreamChunk`, and ends with a
        terminal `kind="stop"` chunk carrying final usage and cost.

        Streaming is not retried — a stream that fails mid-flight has
        already published partial output to the consumer; replaying
        from scratch would emit duplicate chunks. Callers wanting
        retry semantics should accumulate the stream into an
        `LLMResponse` first, then retry the whole call.
        """
        client = await self._ensure_client()
        try:
            response = await asyncio.wait_for(
                client.converse_stream(**request),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise map_unexpected(exc) from exc
        except ClientError as exc:
            raise map_client_error(exc) from exc
        except Exception as exc:
            raise map_unexpected(exc) from exc

        event_stream = response["stream"]
        # tool_use deltas arrive as a stream of input-JSON fragments
        # keyed by Bedrock's contentBlockIndex; we buffer until the
        # matching contentBlockStop and emit one tool_call chunk per
        # complete tool use.
        tool_buffers: dict[int, dict[str, Any]] = {}
        stop_reason: StopReason = "end_turn"
        final_usage = TokenUsage(input_tokens=0, output_tokens=0)

        async for event in event_stream:
            chunk = _process_stream_event(event, tool_buffers)
            if chunk is not None:
                yield chunk
            if "messageStop" in event:
                bedrock_stop = event["messageStop"].get("stopReason", "end_turn")
                stop_reason = _STOP_REASON_MAP.get(bedrock_stop, "other")
            elif "metadata" in event:
                usage_raw = event["metadata"].get("usage", {}) or {}
                final_usage = TokenUsage(
                    input_tokens=int(usage_raw.get("inputTokens", 0)),
                    output_tokens=int(usage_raw.get("outputTokens", 0)),
                    cache_read_tokens=int(usage_raw.get("cacheReadInputTokens", 0)),
                    cache_write_tokens=int(usage_raw.get("cacheWriteInputTokens", 0)),
                )

        cost = compute_cost_usd(
            self._model_id,
            input_tokens=final_usage.input_tokens,
            output_tokens=final_usage.output_tokens,
        )
        yield StreamChunk(
            kind="stop",
            stop_reason=stop_reason,
            usage=final_usage,
            cost_usd=cost,
        )

    async def _ensure_client(self) -> Any:
        """Lazily instantiate the aioboto3 Bedrock Runtime client."""
        if self._client is not None:
            return self._client
        if self._session is None:
            self._session = aioboto3.Session(profile_name=self._aws_profile)
        self._client_cm = self._session.client("bedrock-runtime", region_name=self._region)
        self._client = await self._client_cm.__aenter__()
        return self._client

    def _build_converse_request(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None,
    ) -> dict[str, Any]:
        """Translate framework shapes into Bedrock Converse parameters."""
        request: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": [_message_to_bedrock(m) for m in messages],
        }
        if system:
            request["system"] = [{"text": system}]
        if tools:
            request["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": {"json": t.schema_},
                        }
                    }
                    for t in tools
                ]
            }
        return request

    def _normalise_response(self, raw: dict[str, Any]) -> LLMResponse:
        """Convert a Bedrock Converse response into `LLMResponse`."""
        output_message = raw.get("output", {}).get("message", {}) or {}
        blocks = output_message.get("content", []) or []

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in blocks:
            if "text" in block:
                text_parts.append(block["text"])
            elif "toolUse" in block:
                tu = block["toolUse"]
                tool_calls.append(
                    ToolCall(
                        id=tu["toolUseId"],
                        name=tu["name"],
                        arguments=tu.get("input", {}) or {},
                    )
                )
            # `reasoningContent` blocks (extended thinking) are dropped
            # from the public answer text. The model's reasoning is
            # still counted in usage.outputTokens by Bedrock; surfacing
            # the reasoning trace itself is reserved for a future
            # feature so the public LLMResponse stays simple.

        usage_raw = raw.get("usage", {}) or {}
        input_tokens = int(usage_raw.get("inputTokens", 0))
        output_tokens = int(usage_raw.get("outputTokens", 0))
        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=int(usage_raw.get("cacheReadInputTokens", 0)),
            cache_write_tokens=int(usage_raw.get("cacheWriteInputTokens", 0)),
        )

        bedrock_stop = raw.get("stopReason", "end_turn")
        stop_reason: StopReason = _STOP_REASON_MAP.get(bedrock_stop, "other")

        cost = compute_cost_usd(
            self._model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return LLMResponse(
            content="".join(text_parts),
            tool_calls=tuple(tool_calls),
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=cost,
            model=self._model_id,
            provider=_PROVIDER_NAME,
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _process_stream_event(
    event: dict[str, Any],
    tool_buffers: dict[int, dict[str, Any]],
) -> StreamChunk | None:
    """Translate one Bedrock ConverseStream event into a `StreamChunk`,
    or return `None` if the event is bookkeeping-only.

    Mutates `tool_buffers` in place to accumulate tool-use input JSON
    fragments across deltas; emits a single `kind="tool_call"` chunk
    once the matching `contentBlockStop` arrives.

    `messageStart` / `messageStop` / `metadata` events are handled by
    the caller — they update streaming state (stop_reason, final
    usage) but do not themselves produce per-chunk output.
    """
    if "contentBlockStart" in event:
        _handle_block_start(event["contentBlockStart"], tool_buffers)
        return None
    if "contentBlockDelta" in event:
        return _handle_block_delta(event["contentBlockDelta"], tool_buffers)
    if "contentBlockStop" in event:
        return _handle_block_stop(event["contentBlockStop"], tool_buffers)
    return None


def _handle_block_start(
    start_event: dict[str, Any],
    tool_buffers: dict[int, dict[str, Any]],
) -> None:
    """A `contentBlockStart` event opens a tool-use buffer if the block
    is a tool call; text / reasoning blocks need no setup."""
    block_idx = start_event.get("contentBlockIndex", 0)
    tool_use = start_event.get("start", {}).get("toolUse")
    if tool_use is not None:
        tool_buffers[block_idx] = {
            "id": tool_use["toolUseId"],
            "name": tool_use["name"],
            "input_json": "",
        }


def _handle_block_delta(
    delta_event: dict[str, Any],
    tool_buffers: dict[int, dict[str, Any]],
) -> StreamChunk | None:
    """A `contentBlockDelta` event carries one of: text fragment,
    reasoningContent fragment, or tool-use input JSON fragment."""
    delta = delta_event.get("delta", {}) or {}
    block_idx = delta_event.get("contentBlockIndex", 0)
    if "text" in delta:
        return StreamChunk(kind="text", delta=delta["text"])
    if "reasoningContent" in delta:
        text = (delta["reasoningContent"] or {}).get("text", "")
        return StreamChunk(kind="thinking", delta=text) if text else None
    if "toolUse" in delta:
        buffered = tool_buffers.get(block_idx)
        if buffered is not None:
            buffered["input_json"] += delta["toolUse"].get("input", "")
    return None


def _handle_block_stop(
    stop_event: dict[str, Any],
    tool_buffers: dict[int, dict[str, Any]],
) -> StreamChunk | None:
    """A `contentBlockStop` event closes a block; if it was a tool-use
    block, emit the assembled `ToolCall` chunk."""
    block_idx = stop_event.get("contentBlockIndex", 0)
    buffered = tool_buffers.pop(block_idx, None)
    if buffered is None:
        return None
    return StreamChunk(
        kind="tool_call",
        tool_call=ToolCall(
            id=buffered["id"],
            name=buffered["name"],
            arguments=_safe_parse_tool_input(buffered["input_json"]),
        ),
    )


def _safe_parse_tool_input(raw: str) -> dict[str, Any]:
    """Parse a tool-use input JSON fragment string into a dict.

    Bedrock streams tool inputs as a sequence of JSON-string deltas
    that should concatenate into valid JSON. If the LLM emits a
    truncated stream (rare but possible on stop_reason="max_tokens"),
    we surface an empty arguments dict rather than crashing the
    consumer; tool-use stop reasons let the caller decide what to do.
    """
    text = raw.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        log.warning(
            "agentforge-bedrock: failed to parse tool_use input JSON fragment %r; "
            "emitting empty arguments dict.",
            text[:200],
        )
        return {}
    return parsed if isinstance(parsed, dict) else {}


def accumulate_stream(stream: AsyncIterator[StreamChunk]) -> _StreamAccumulator:
    """Adapter: consume a `BedrockClient.stream()` into one `LLMResponse`.

    Useful for callers that get a stream back but want the same shape
    as `call()`. Drops `kind="thinking"` chunks from the public answer
    (consistent with `call_with_thinking`'s reasoningContent handling)
    while still surfacing tool calls and final usage / cost.

    Returns an awaitable adapter — `await accumulate_stream(stream)`.
    """
    return _StreamAccumulator(stream)


class _StreamAccumulator:
    """Internal awaitable adapter for `accumulate_stream`."""

    __slots__ = ("_stream",)

    def __init__(self, stream: AsyncIterator[StreamChunk]) -> None:
        self._stream = stream

    def __await__(self) -> Any:
        return self._consume().__await__()

    async def _consume(self) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        stop_reason: StopReason = "end_turn"
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        cost = 0.0
        model = "bedrock-stream"
        async for chunk in self._stream:
            if chunk.kind == "text":
                text_parts.append(chunk.delta)
            elif chunk.kind == "tool_call" and chunk.tool_call is not None:
                tool_calls.append(chunk.tool_call)
            elif chunk.kind == "stop":
                if chunk.stop_reason is not None:
                    stop_reason = chunk.stop_reason
                if chunk.usage is not None:
                    usage = chunk.usage
                cost = chunk.cost_usd
            # kind="thinking" deltas are dropped from the public answer.
        return LLMResponse(
            content="".join(text_parts),
            tool_calls=tuple(tool_calls),
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=cost,
            model=model,
            provider=_PROVIDER_NAME,
        )


def _inject_cache_points(request: dict[str, Any], breakpoints: list[int]) -> None:
    """Append a Bedrock cachePoint block after each indexed message's
    content list. Indices outside `[0, len(messages))` are dropped.

    Bedrock allows multiple cache points; the limit varies by model
    (today: 4 for current Anthropic Claude). We don't enforce that —
    if a caller exceeds the limit, Bedrock returns a ValidationError
    which our error mapper surfaces as `ProviderError`.
    """
    bedrock_messages: list[dict[str, Any]] = request.get("messages", [])
    n_messages = len(bedrock_messages)
    seen: set[int] = set()
    for idx in breakpoints:
        if idx in seen or not 0 <= idx < n_messages:
            continue
        seen.add(idx)
        content = bedrock_messages[idx].setdefault("content", [])
        content.append({"cachePoint": {"type": "default"}})


def _message_to_bedrock(message: Message) -> dict[str, Any]:
    """Translate one framework `Message` into a Bedrock content block.

    Bedrock Converse only recognises `"user"` and `"assistant"` roles.
    `"system"` is hoisted to the request's `system` field by the
    caller; `"tool"` messages are encoded as user-role tool results.
    """
    if message.role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": message.tool_call_id or "",
                        "content": [{"text": message.content}],
                    }
                }
            ],
        }
    if message.role == "system":
        # Should be hoisted by the caller; keep a defensive fallback.
        return {"role": "user", "content": [{"text": message.content}]}
    return {
        "role": message.role,
        "content": [{"text": message.content}],
    }


__all__ = ["BedrockClient"]
