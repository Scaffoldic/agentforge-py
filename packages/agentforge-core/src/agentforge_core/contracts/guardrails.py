"""Guardrail ABCs (feat-018).

Three locked ABCs:

- `InputValidator.validate(content, context)` — runs before each
  LLM call on the user-visible input.
- `OutputValidator.validate(content, context)` — runs after each
  LLM call on the model's output.
- `ToolCallGate.authorize(tool_name, tool, args, context)` — runs
  before tool dispatch.

All three return `ValidationResult`. Implementations are async so
they can integrate with HTTP-based validators (LLM Guard,
Presidio, Llama Guard) without blocking the event loop.

The `name: str` ClassVar identifies the validator in audit events
and config-resolution paths.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from agentforge_core.values.guardrails import ValidationResult

if TYPE_CHECKING:
    from agentforge_core.contracts.tool import Tool


class InputValidator(ABC):
    """Validates user input before the agent's first LLM call.

    Subclasses set ClassVars `name`, `description`, and
    `cost_estimate_ms` (rough per-call latency in milliseconds).
    """

    name: ClassVar[str]
    description: ClassVar[str]
    cost_estimate_ms: ClassVar[int] = 0

    @abstractmethod
    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        """Validate `content`. `context` carries `run_id`, `project`,
        `agent`, and any per-call metadata."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        _require_attrs(cls, ("name", "description"))


class OutputValidator(ABC):
    """Validates the model's output after each LLM call.

    Output validators MAY redact: set `redacted_content` on the
    returned `ValidationResult` to the post-redaction text. The
    framework forwards that content downstream when
    `policy.on_output_violation == "redact"`.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    cost_estimate_ms: ClassVar[int] = 0

    @abstractmethod
    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        """Validate `content` (the LLM's text output)."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        _require_attrs(cls, ("name", "description"))


class ToolCallGate(ABC):
    """Authorises a tool invocation before dispatch.

    Receives the tool instance so gates can inspect `tool.capabilities`
    or other static metadata.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    cost_estimate_ms: ClassVar[int] = 0

    @abstractmethod
    async def authorize(
        self,
        tool_name: str,
        tool: Tool,
        args: dict[str, Any],
        context: dict[str, Any],
    ) -> ValidationResult:
        """Authorise the upcoming tool call."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        _require_attrs(cls, ("name", "description"))


def _require_attrs(cls: type, attrs: tuple[str, ...]) -> None:
    """Enforce the ClassVar contract on concrete subclasses."""
    import inspect  # noqa: PLC0415

    if inspect.isabstract(cls):
        return
    for attr in attrs:
        if attr not in cls.__dict__ and not _inherited(cls, attr):
            msg = (
                f"{cls.__name__} must declare class attribute {attr!r} "
                "(every guardrail validator carries a stable name and "
                "human-readable description for audit events)."
            )
            raise TypeError(msg)


def _inherited(cls: type, attr: str) -> bool:
    for base in cls.__mro__[1:]:
        if base is object:
            continue
        if attr in base.__dict__ and base.__module__ != cls.__module__:
            return True
    return False


__all__ = [
    "InputValidator",
    "OutputValidator",
    "ToolCallGate",
]
