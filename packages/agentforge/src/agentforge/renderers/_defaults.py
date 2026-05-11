"""Pre-population helper for `RendererRegistry.default()` (feat-008).

Kept in a separate module so `registry.py` can lazy-import it inside
`default()` and avoid a top-level cycle between the registry and the
concrete renderer modules (which themselves import the variants from
`agentforge.findings`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentforge.findings import MultiSpanFinding, NarrativeFinding, PatchFinding, SimpleFinding
from agentforge.renderers.markdown import MarkdownRenderer
from agentforge.renderers.patch_applier import PatchApplierRenderer
from agentforge.renderers.scorecard import ScorecardRenderer
from agentforge.renderers.span_table import SpanTableRenderer

if TYPE_CHECKING:
    from agentforge.renderers.registry import RendererRegistry


def populate_defaults(registry: RendererRegistry) -> None:
    """Register the four built-in renderers on `registry`.

    Idempotent — re-registering the same exact type replaces the
    prior entry (see `RendererRegistry.register`).
    """
    registry.register(SimpleFinding, ScorecardRenderer())
    registry.register(PatchFinding, PatchApplierRenderer())
    registry.register(NarrativeFinding, MarkdownRenderer())
    registry.register(MultiSpanFinding, SpanTableRenderer())
