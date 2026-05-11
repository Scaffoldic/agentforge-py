"""`allowlist` — bare-name allowlist for tool dispatch (feat-018).

If `allowed` is set, only the tools whose names appear in it can
run. Pairs naturally with `capability_check` to add a second
restrictive layer.
"""

from __future__ import annotations

from typing import Any, ClassVar

from agentforge_core.contracts.guardrails import ToolCallGate
from agentforge_core.contracts.tool import Tool
from agentforge_core.resolver import register
from agentforge_core.values.guardrails import ValidationResult


@register("guardrails.tool_gates", "allowlist")
class Allowlist(ToolCallGate):
    """Only tools whose name appears in `allowed` can run."""

    name: ClassVar[str] = "allowlist"
    description: ClassVar[str] = (
        "Permits only tools whose names appear in `allowed`. Everything else is blocked."
    )
    cost_estimate_ms: ClassVar[int] = 0

    def __init__(self, *, allowed: list[str] | None = None) -> None:
        self._allowed = set(allowed or ())

    async def authorize(
        self,
        tool_name: str,
        tool: Tool,
        args: dict[str, Any],
        context: dict[str, Any],
    ) -> ValidationResult:
        del tool, args, context
        if tool_name in self._allowed:
            return ValidationResult.ok()
        return ValidationResult(
            passed=False,
            score=0.0,
            violations=("not_in_allowlist",),
            metadata={"tool": tool_name, "allowed": sorted(self._allowed)},
        )


__all__ = ["Allowlist"]
