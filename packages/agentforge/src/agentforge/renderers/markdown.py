"""`MarkdownRenderer` — narrative rendering for `NarrativeFinding`.

text format: question (message) + body + "References:" footer.
markdown format: heading + body + "## References" section with a list.
"""

from __future__ import annotations

from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.renderer import FindingRenderer

from agentforge.findings import NarrativeFinding

_SUPPORTED_FORMATS = frozenset({"text", "markdown"})


class MarkdownRenderer(FindingRenderer):
    """Renders `NarrativeFinding` as prose with citations."""

    def render(self, finding: Finding, format: str = "text") -> str:
        if format not in _SUPPORTED_FORMATS:
            raise ValueError(
                f"MarkdownRenderer supports {sorted(_SUPPORTED_FORMATS)}; got {format!r}"
            )
        if not isinstance(finding, NarrativeFinding):
            raise TypeError(
                f"MarkdownRenderer renders NarrativeFinding; got {type(finding).__name__}"
            )

        if format == "markdown":
            heading = f"## {finding.message}"
            refs_section = ""
            if finding.references:
                refs_lines = "\n".join(f"- {r}" for r in finding.references)
                refs_section = f"\n\n### References\n\n{refs_lines}"
            return f"{heading}\n\n{finding.body}{refs_section}"

        refs_section = ""
        if finding.references:
            refs_section = "\n\nReferences:\n" + "\n".join(f"  - {r}" for r in finding.references)
        return f"{finding.message}\n\n{finding.body}{refs_section}"

    def supports(self, finding_type: type) -> bool:
        return issubclass(finding_type, NarrativeFinding)
