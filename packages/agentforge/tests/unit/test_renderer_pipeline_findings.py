"""Renderer-compat sanity check (feat-015 chunk 5).

`PipelineResult.findings` is `list[Finding]` (Protocol). The
existing `RendererRegistry` is finding-type-agnostic, so the
pipeline output should flow through the shipped renderers without
any glue code.
"""

from __future__ import annotations

from agentforge.findings import (
    Patch,
    PatchFinding,
    SimpleFinding,
)
from agentforge.renderers import RendererRegistry
from agentforge_core.values.pipeline import PipelineResult


def test_simple_and_patch_findings_render_via_default_registry() -> None:
    result = PipelineResult(
        findings=(
            SimpleFinding(severity="warning", category="lint", message="trailing ws"),
            PatchFinding(
                severity="suggestion",
                category="patch",
                message="Apply formatter",
                patch=Patch(file="a.py", diff="@@ -1 +1 @@\n-x\n+y\n", hunk_count=1),
                rationale="ruff format",
                confidence=0.9,
            ),
        )
    )
    registry = RendererRegistry.default()
    rendered = [registry.get(f).render(f) for f in result.findings]
    assert all(isinstance(r, str) and r for r in rendered)
    # The simple-finding renderer (scorecard) emits the category.
    assert any("lint" in r for r in rendered)
    # The patch-finding renderer emits the diff body.
    assert any("@@" in r for r in rendered)
