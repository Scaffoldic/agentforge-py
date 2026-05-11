"""`LlamaGuardInput` / `LlamaGuardOutput` — Meta Llama Guard 3 (feat-018).

Llama Guard is a chat model — we send it the user-or-assistant turn
and parse the response. The response is `safe` (clean) or `unsafe`
followed by category codes `S1..S14`.

The classifier needs an `LLMClient`; pass one explicitly (tests do)
or supply a `model: "<provider>:<id>"` string and the framework's
resolver will instantiate it.
"""

from __future__ import annotations

from typing import Any, ClassVar

from agentforge_core.contracts.guardrails import InputValidator, OutputValidator
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import Resolver, parse_model_string
from agentforge_core.values.guardrails import ValidationResult
from agentforge_core.values.messages import Message

_LLAMAGUARD_PROMPT = (
    "Task: Check if there is unsafe content in the user message according to "
    "the Llama Guard safety policy. Respond with `safe` or `unsafe` followed "
    "by a comma-separated list of violated categories (S1..S14)."
)


class _LlamaGuardMixin:
    """Shared construction surface for the input + output adapters."""

    name: ClassVar[str]
    description: ClassVar[str]
    cost_estimate_ms: ClassVar[int] = 80

    def __init__(
        self,
        *,
        model: str | None = None,
        client: LLMClient | None = None,
    ) -> None:
        if client is None and model is None:
            msg = "LlamaGuard adapter requires either `model` or an explicit `client`."
            raise ValueError(msg)
        self._client = client if client is not None else self._resolve_client(model)

    def _resolve_client(self, model: str | None) -> LLMClient:
        if model is None:  # pragma: no cover — guarded in __init__
            msg = "model required"
            raise ValueError(msg)
        provider, model_id = parse_model_string(model)
        cls = Resolver.global_().resolve("providers", provider)
        instance = cls(model_id=model_id)
        if not isinstance(instance, LLMClient):
            msg = f"Resolved provider {provider!r} ({cls.__name__}) does not implement LLMClient."
            raise ModuleError(msg)
        return instance


class LlamaGuardInput(_LlamaGuardMixin, InputValidator):
    """Llama Guard 3 — classifies the user input."""

    name: ClassVar[str] = "llamaguard"
    description: ClassVar[str] = (
        "Meta Llama Guard 3 classifier applied to the user input. Returns "
        "`unsafe` + category codes when the user message triggers the "
        "policy; we map any `unsafe` reply to a guardrail violation."
    )

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del context
        return await _classify(self._client, role="user", text=content)


class LlamaGuardOutput(_LlamaGuardMixin, OutputValidator):
    """Llama Guard 3 — classifies the model's output."""

    name: ClassVar[str] = "llamaguard"
    description: ClassVar[str] = "Meta Llama Guard 3 classifier applied to the assistant output."

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del context
        return await _classify(self._client, role="assistant", text=content)


async def _classify(client: LLMClient, *, role: str, text: str) -> ValidationResult:
    response = await client.call(
        system=_LLAMAGUARD_PROMPT,
        messages=[Message(role=role, content=text)],  # type: ignore[arg-type]
    )
    text_out = response.content.strip().lower()
    if text_out.startswith("safe"):
        return ValidationResult.ok()
    categories = _parse_categories(text_out)
    return ValidationResult(
        passed=False,
        score=0.0,
        violations=tuple(categories) if categories else ("llamaguard_unsafe",),
        metadata={"raw": response.content},
    )


def _parse_categories(text: str) -> list[str]:
    """Pluck `S1..S14` category codes from a Llama Guard reply."""
    if "unsafe" not in text:
        return []
    body = text.split("unsafe", 1)[1].strip()
    if not body:
        return []
    return [c.strip() for c in body.split(",") if c.strip().startswith("s")]


__all__ = ["LlamaGuardInput", "LlamaGuardOutput"]
