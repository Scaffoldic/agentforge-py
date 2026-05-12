"""`pipeline_findings` — the built-in tool that surfaces a Pipeline's
output back to the LLM (feat-015).

The agent wires one `PipelineFindingsTool` instance into its tool set
whenever `Agent(pipeline=...)` is set. Before each `Agent.run()`, the
agent stashes the freshly produced findings on the tool via
``_set_cache(...)``. The LLM can then call ``pipeline_findings()``
with optional ``category`` / ``severity`` filters to retrieve them as
JSON-friendly dicts.

Returning serialized dicts (via ``model_dump(mode="json")`` when
available, else ``to_dict()``) keeps the contract tolerant of
non-Pydantic Finding shapes — see ``agentforge_core.contracts.finding``.
"""

from __future__ import annotations

from typing import Any

from agentforge_core.contracts.tool import Tool
from pydantic import BaseModel, ConfigDict, Field


class PipelineFindingsInput(BaseModel):
    """Filter parameters for `pipeline_findings`."""

    model_config = ConfigDict(extra="forbid")

    category: str | None = Field(
        default=None,
        description="If set, return only findings whose `category` matches.",
    )
    severity: str | None = Field(
        default=None,
        description="If set, return only findings whose `severity` matches.",
    )


class PipelineFindingsTool(Tool):
    """Built-in tool that lets the LLM re-query pipeline output.

    The agent caches the latest `PipelineResult.findings` on this
    instance at the start of every `Agent.run()`. The tool's `run()`
    filters the cache and returns serializable dicts.
    """

    name = "pipeline_findings"
    description = (
        "List the findings produced by this agent's deterministic pipeline. "
        "Optional filters: `category` (e.g. 'lint', 'coverage') and `severity` "
        "(e.g. 'error', 'warning', 'info'). Returns a list of dicts."
    )
    input_schema = PipelineFindingsInput

    def __init__(self) -> None:
        self._cached_findings: list[Any] = []

    def _set_cache(self, findings: list[Any]) -> None:
        """Replace the cached findings (called by `Agent.run()`)."""
        self._cached_findings = list(findings)

    async def run(self, **kwargs: Any) -> list[dict[str, Any]]:
        params = PipelineFindingsInput.model_validate(kwargs)
        out: list[dict[str, Any]] = []
        for f in self._cached_findings:
            if params.category is not None and getattr(f, "category", None) != params.category:
                continue
            if params.severity is not None and getattr(f, "severity", None) != params.severity:
                continue
            out.append(_serialise_finding(f))
        return out


def _serialise_finding(f: Any) -> dict[str, Any]:
    dump = getattr(f, "model_dump", None)
    if callable(dump):
        result = dump(mode="json")
        if isinstance(result, dict):
            return result
    to_dict = getattr(f, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        if isinstance(result, dict):
            return result
    # Best-effort fallback for arbitrary Finding-shaped objects.
    return {
        "severity": getattr(f, "severity", None),
        "category": getattr(f, "category", None),
        "message": getattr(f, "message", None),
    }


__all__ = ["PipelineFindingsInput", "PipelineFindingsTool"]
