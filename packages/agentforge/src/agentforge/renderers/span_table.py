"""`SpanTableRenderer` — multi-span rendering for `MultiSpanFinding`.

text format: header + one block per span (`file:start-end  excerpt`).
markdown format: header + GFM table (file | lines | excerpt).
"""

from __future__ import annotations

from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.renderer import FindingRenderer

from agentforge.findings import MultiSpanFinding, Span

_SUPPORTED_FORMATS = frozenset({"text", "markdown"})


class SpanTableRenderer(FindingRenderer):
    """Renders `MultiSpanFinding` as a per-span block (text) or table (md)."""

    def render(self, finding: Finding, format: str = "text") -> str:
        if format not in _SUPPORTED_FORMATS:
            raise ValueError(
                f"SpanTableRenderer supports {sorted(_SUPPORTED_FORMATS)}; got {format!r}"
            )
        if not isinstance(finding, MultiSpanFinding):
            raise TypeError(
                f"SpanTableRenderer renders MultiSpanFinding; got {type(finding).__name__}"
            )

        header = f"[{finding.severity}] {finding.category}: {finding.message}"

        if format == "markdown":
            rows = "\n".join(self._md_row(s) for s in finding.spans)
            table = "| file | lines | excerpt |\n|---|---|---|\n" + rows
            footer = (
                f"\n\n**Recommendation:** {finding.recommendation}"
                if finding.recommendation
                else ""
            )
            return (
                f"## {finding.message}\n\n"
                f"severity: `{finding.severity}` — "
                f"category: `{finding.category}`\n\n"
                f"{table}{footer}"
            )

        blocks = "\n".join(self._text_block(s) for s in finding.spans)
        footer = f"\n\nrecommendation: {finding.recommendation}" if finding.recommendation else ""
        return f"{header}\n\n{blocks}{footer}"

    def supports(self, finding_type: type) -> bool:
        return issubclass(finding_type, MultiSpanFinding)

    @staticmethod
    def _text_block(span: Span) -> str:
        location = f"{span.file}:{span.start_line}"
        if span.end_line != span.start_line:
            location = f"{span.file}:{span.start_line}-{span.end_line}"
        excerpt = f"\n    {span.excerpt}" if span.excerpt else ""
        return f"  - {location}{excerpt}"

    @staticmethod
    def _md_row(span: Span) -> str:
        lines = (
            str(span.start_line)
            if span.start_line == span.end_line
            else f"{span.start_line}-{span.end_line}"
        )
        # Escape pipes in excerpts so we don't break the table.
        excerpt = span.excerpt.replace("|", "\\|")
        return f"| `{span.file}` | {lines} | `{excerpt}` |"
