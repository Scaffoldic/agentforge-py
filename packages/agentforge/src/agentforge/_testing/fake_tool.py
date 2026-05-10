"""`FakeTool` — minimal scripted-response `Tool` for unit tests
(feat-004 chunk 5).

Replaces any tool with a stub during tests. Two construction forms:

    from agentforge._testing import FakeTool

    # 1. Static return value
    web_search = FakeTool.fake("web_search", "stub result")

    # 2. Callable that computes the response from the call args
    web_search = FakeTool.fake(
        "web_search",
        lambda **kwargs: f"results for {kwargs['query']!r}",
    )

The fake honours the same locked `Tool` ABC: it has a `name`,
`description`, `input_schema` (a permissive `dict`-shaped model that
accepts any kwargs), and a `run(**kwargs)` method. `Agent(tools=
[fake, ...])` works without other changes.

Replaced by feat-016's richer testing API; this is the minimum
surface to support feat-004 / feat-002 tests today.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from agentforge_core.contracts.tool import Tool
from pydantic import BaseModel, ConfigDict


class _PermissiveInput(BaseModel):
    """Input schema for `FakeTool` — accepts any kwargs.

    Real `Tool` implementations declare a strict Pydantic model so
    bad LLM tool-calls are rejected at the dispatch boundary; the
    fake intentionally relaxes this so test code can pass arbitrary
    kwargs without first defining a schema.
    """

    model_config = ConfigDict(extra="allow")


_FakeFn = Callable[..., Any] | Callable[..., Awaitable[Any]]


class FakeTool(Tool):
    """Test-only `Tool` that returns scripted responses.

    Construct via `FakeTool.fake(name, response_or_fn)` rather than
    the bare class so the per-instance `name` / `description` work
    without subclassing.
    """

    name: ClassVar[str] = "fake"
    description: ClassVar[str] = "Test-only stub tool."
    input_schema: ClassVar[type[BaseModel]] = _PermissiveInput
    capabilities: ClassVar[frozenset[str]] = frozenset()
    calls: list[dict[str, Any]]
    """Per-instance recorded `run` invocation kwargs. Populated by
    `fake()`-built instances; bare-class fallback keeps it empty."""

    @classmethod
    def fake(
        cls,
        name: str,
        response: Any | _FakeFn,
        *,
        description: str | None = None,
        capabilities: frozenset[str] | set[str] = frozenset(),
    ) -> FakeTool:
        """Build a fake tool with the given name and response.

        `response` can be:
          - A static value (returned as-is from every `run` call)
          - A sync callable: `fn(**kwargs) -> Any`
          - An async callable: `async fn(**kwargs) -> Any`

        Records every call in `self.calls` for assertions.
        """
        # Synthesize a class so `name` / `description` / `capabilities`
        # become per-fake. type() avoids subclass-scope dance from the
        # @tool decorator.
        is_async = _is_async_callable(response)
        is_callable = callable(response) and not isinstance(response, type)

        async def _run(self: FakeTool, **kwargs: Any) -> Any:
            self.calls.append(dict(kwargs))
            if is_callable:
                if is_async:
                    return await response(**kwargs)
                return response(**kwargs)
            return response

        cls_namespace: dict[str, Any] = {
            "name": name,
            "description": description or f"Fake {name} tool.",
            "input_schema": _PermissiveInput,
            "capabilities": frozenset(capabilities),
            "run": _run,
            "calls": [],
        }
        synthesized = type(f"Fake{name.title()}Tool", (cls,), cls_namespace)
        instance: FakeTool = synthesized()
        return instance

    async def run(self, **kwargs: Any) -> Any:  # noqa: ARG002 — bare-class fallback ignores kwargs
        """Default `run` body — overridden by `fake()` instances; the
        bare-class fallback returns the empty string."""
        return ""


def _is_async_callable(obj: Any) -> bool:
    """True for `async def` functions and partials wrapping them."""
    return asyncio.iscoroutinefunction(obj)


__all__ = ["FakeTool"]
