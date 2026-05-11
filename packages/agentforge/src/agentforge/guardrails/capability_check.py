"""`capability_check` — denies tools tagged `destructive` unless
explicitly allowlisted (feat-018).

Tools declare their capabilities via the `Tool.capabilities`
ClassVar (feat-004). Any tool that includes `"destructive"` in
its capability set is blocked by this gate by default; the
agent's config can opt-in specific tools via the
`destructive_allow` list.
"""

from __future__ import annotations

from typing import Any, ClassVar

from agentforge_core.contracts.guardrails import ToolCallGate
from agentforge_core.contracts.tool import Tool
from agentforge_core.resolver import register
from agentforge_core.values.guardrails import ValidationResult

_DESTRUCTIVE = "destructive"


@register("guardrails.tool_gates", "capability_check")
class CapabilityCheck(ToolCallGate):
    """Block `destructive` tools unless explicitly allowlisted."""

    name: ClassVar[str] = "capability_check"
    description: ClassVar[str] = (
        "Denies any tool whose capabilities include 'destructive' unless "
        "the tool name appears in `destructive_allow`."
    )
    cost_estimate_ms: ClassVar[int] = 0

    def __init__(self, *, destructive_allow: list[str] | None = None) -> None:
        self._allow = set(destructive_allow or ())

    async def authorize(
        self,
        tool_name: str,
        tool: Tool,
        args: dict[str, Any],
        context: dict[str, Any],
    ) -> ValidationResult:
        del args, context
        caps = set(type(tool).capabilities)
        if _DESTRUCTIVE not in caps:
            return ValidationResult.ok()
        if tool_name in self._allow:
            return ValidationResult.ok()
        return ValidationResult(
            passed=False,
            score=0.0,
            violations=("destructive_not_allowlisted",),
            metadata={"tool": tool_name, "capabilities": sorted(caps)},
        )


__all__ = ["CapabilityCheck"]
