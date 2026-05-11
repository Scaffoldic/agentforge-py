"""Renderer registry + built-in renderers for `Finding` variants (feat-008).

`RendererRegistry` maps a `Finding` instance to a `FindingRenderer`
using isinstance-based dispatch with a most-specific-wins rule. The
four built-in renderers (shipped in chunk 3) handle the four shipped
variants.

A `default()` factory returns a pre-populated registry — the common
case for agent code. Custom agents register additional renderers for
their own variants.
"""

from __future__ import annotations

from agentforge.renderers.markdown import MarkdownRenderer
from agentforge.renderers.patch_applier import PatchApplierRenderer
from agentforge.renderers.registry import MissingRendererError, RendererRegistry
from agentforge.renderers.scorecard import ScorecardRenderer
from agentforge.renderers.span_table import SpanTableRenderer

__all__ = [
    "MarkdownRenderer",
    "MissingRendererError",
    "PatchApplierRenderer",
    "RendererRegistry",
    "ScorecardRenderer",
    "SpanTableRenderer",
]
