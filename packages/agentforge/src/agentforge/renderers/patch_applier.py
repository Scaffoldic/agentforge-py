"""`PatchApplierRenderer` — diff rendering for `PatchFinding`.

text format: header line + unified-diff body.
markdown format: same content wrapped in a fenced ` ```diff ` block.

The renderer does NOT apply the patch — that's the caller's
responsibility. The name reflects the typical downstream use, not what
this class does.
"""

from __future__ import annotations

from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.renderer import FindingRenderer

from agentforge.findings import PatchFinding

_SUPPORTED_FORMATS = frozenset({"text", "markdown"})


class PatchApplierRenderer(FindingRenderer):
    """Renders `PatchFinding` as a unified diff (plain or fenced)."""

    def render(self, finding: Finding, format: str = "text") -> str:
        if format not in _SUPPORTED_FORMATS:
            raise ValueError(
                f"PatchApplierRenderer supports {sorted(_SUPPORTED_FORMATS)}; got {format!r}"
            )
        if not isinstance(finding, PatchFinding):
            raise TypeError(
                f"PatchApplierRenderer renders PatchFinding; got {type(finding).__name__}"
            )

        header = (
            f"[{finding.severity}] {finding.category}: {finding.message}\n"
            f"file: {finding.patch.file}  (confidence={finding.confidence:.2f})\n"
            f"rationale: {finding.rationale}"
        )

        diff_body = finding.patch.diff.rstrip("\n")
        if format == "markdown":
            return f"{header}\n\n```diff\n{diff_body}\n```"
        return f"{header}\n\n{diff_body}"

    def supports(self, finding_type: type) -> bool:
        return issubclass(finding_type, PatchFinding)
