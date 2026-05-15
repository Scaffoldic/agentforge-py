"""`LiteLLMClient` — `LLMClient` over LiteLLM's unified router."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import register_provider
from agentforge_core.values.messages import (
    LLMResponse,
    Message,
    StopReason,
    TokenUsage,
    ToolCall,
    ToolSpec,
)

if TYPE_CHECKING:
    from agentforge_litellm._runner import LiteLLMRunner


_PROVIDER_NAME = "litellm"
_DEFAULT_TIMEOUT_SECONDS = 60.0

_FINISH_REASON_MAP: dict[str, StopReason] = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "content_filter": "other",
}


@register_provider("litellm")
class LiteLLMClient(LLMClient):
    """`LLMClient` over LiteLLM. `model` is whatever LiteLLM accepts."""

    def __init__(
        self,
        *,
        model_id: str,
        runner: LiteLLMRunner | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not model_id:
            raise ValueError("model_id must be a non-empty string")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._runner = runner if runner is not None else _build_sdk_runner()
        self._model = model_id
        self._timeout_seconds = timeout_seconds
        self._extra = dict(extra) if extra else None

    @classmethod
    def from_config(
        cls,
        *,
        model: str,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        extra: dict[str, Any] | None = None,
    ) -> LiteLLMClient:  # pragma: no cover — `-m live` only.
        return cls(model_id=model, timeout_seconds=timeout_seconds, extra=extra)

    def capabilities(self) -> set[str]:
        # LiteLLM normalises tool-use across backends; everything else
        # (caching, thinking, streaming, vision) varies per provider.
        # Conservatively expose only the lowest-common-denominator
        # capability — callers wanting more should use a native sister
        # package.
        return {"tools"}

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        raw = await self._runner.acompletion(
            model=self._model,
            messages=_build_messages(system, messages),
            tools=_tools_to_litellm(tools),
            timeout_s=self._timeout_seconds,
            extra=self._extra,
        )
        return self._normalise_response(raw)

    async def close(self) -> None:
        await self._runner.close()

    def _normalise_response(self, raw: dict[str, Any]) -> LLMResponse:
        choices = raw.get("choices") or []
        choice0 = choices[0] if choices else {}
        msg = choice0.get("message") or {}

        content = msg.get("content") or ""
        if isinstance(content, list):
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

        # LiteLLM surfaces a `_hidden_params.response_cost` field with
        # an upstream-computed USD figure. We trust it when present;
        # otherwise default 0.0 (the framework's BudgetPolicy can also
        # use its own price table).
        hidden = raw.get("_hidden_params") or {}
        cost = float(hidden.get("response_cost") or 0.0)

        return LLMResponse(
            content=content,
            tool_calls=tuple(tool_calls),
            stop_reason=stop_reason,
            usage=usage,
            cost_usd=max(cost, 0.0),
            model=raw.get("model") or self._model,
            provider=_PROVIDER_NAME,
        )


def _build_messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        if m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id or "", "content": m.content})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def _tools_to_litellm(tools: list[ToolSpec] | None) -> list[dict[str, Any]] | None:
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


def _build_sdk_runner() -> LiteLLMRunner:  # pragma: no cover — `-m live` only.
    try:
        import litellm  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "litellm is not installed. Install via "
            "`pip install agentforge-litellm[litellm]` to use the production runner."
        )
        raise ModuleError(msg) from exc

    from agentforge_litellm._runner import _LiteLLMSDKRunner  # noqa: PLC0415

    return _LiteLLMSDKRunner(litellm)


__all__ = ["LiteLLMClient"]
