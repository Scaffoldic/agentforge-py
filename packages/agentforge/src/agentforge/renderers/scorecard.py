"""`ScorecardRenderer` — text/markdown rendering for `SimpleFinding`.

text format: `[severity] category: message (file:line) — recommendation`.
markdown format: a single GFM table row (header is the caller's job).
"""

from __future__ import annotations

from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.renderer import FindingRenderer

from agentforge.findings import SimpleFinding

_SUPPORTED_FORMATS = frozenset({"text", "markdown"})


class ScorecardRenderer(FindingRenderer):
    """Renders `SimpleFinding` as a severity-tagged line or table row."""

    def render(self, finding: Finding, format: str = "text") -> str:
        if format not in _SUPPORTED_FORMATS:
            raise ValueError(
                f"ScorecardRenderer supports {sorted(_SUPPORTED_FORMATS)}; got {format!r}"
            )
        if not isinstance(finding, SimpleFinding):
            raise TypeError(
                f"ScorecardRenderer renders SimpleFinding; got {type(finding).__name__}"
            )

        if format == "markdown":
            return self._render_markdown(finding)
        return self._render_text(finding)

    def supports(self, finding_type: type) -> bool:
        return issubclass(finding_type, SimpleFinding)

    @staticmethod
    def _render_text(finding: SimpleFinding) -> str:
        location = ""
        if finding.file:
            location = f" ({finding.file}"
            if finding.line is not None:
                location += f":{finding.line}"
            location += ")"
        trailer = f" — {finding.recommendation}" if finding.recommendation else ""
        rule = f" [{finding.rule_id}]" if finding.rule_id else ""
        return (
            f"[{finding.severity}]{rule} {finding.category}: {finding.message}{location}{trailer}"
        )

    @staticmethod
    def _render_markdown(finding: SimpleFinding) -> str:
        location = finding.file
        if finding.file and finding.line is not None:
            location = f"{finding.file}:{finding.line}"
        return (
            f"| {finding.severity} | {finding.category} | "
            f"{finding.message} | {location} | {finding.recommendation} |"
        )
