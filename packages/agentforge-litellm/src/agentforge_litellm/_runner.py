"""LiteLLM runner Protocol + production SDK wrapper."""

from __future__ import annotations

from typing import Any, Protocol, cast


class LiteLLMRunner(Protocol):
    """Lifecycle Protocol for one LiteLLM completion call."""

    async def acompletion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:  # pragma: no cover
        """Issue a non-streaming completion."""
        ...

    async def close(self) -> None:  # pragma: no cover
        ...


class _LiteLLMSDKRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner calling ``litellm.acompletion``."""

    def __init__(self, module: Any) -> None:
        self._litellm = module

    async def acompletion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        timeout_s: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "timeout": timeout_s,
        }
        if tools:
            kwargs["tools"] = tools
        if extra:
            kwargs.update(extra)
        result = await self._litellm.acompletion(**kwargs)
        # LiteLLM returns a ModelResponse object with .model_dump().
        return cast("dict[str, Any]", result.model_dump(mode="python", exclude_none=False))

    async def close(self) -> None:
        # `litellm` is a module-level singleton; nothing to release.
        return None


__all__ = ["LiteLLMRunner"]
