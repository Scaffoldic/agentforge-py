"""`FindingRenderer` — locked contract for rendering Findings to text.

Per feat-008 / ADR-0007, this ABC is part of the framework's stable
surface. Concrete renderers ship in `agentforge.renderers` and resolve
through `RendererRegistry`; agent / module authors implement this ABC
to ship custom renderers for their own `Finding` variants.

Rendering is intentionally text-out. Format strings are advisory —
implementations should accept at least `"text"` (plain) and
`"markdown"` (markdown-formatted), and may support additional formats
they declare.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentforge_core.contracts.finding import Finding


class FindingRenderer(ABC):
    """Render a `Finding` to a string in one of several formats.

    Implementations are typically pinned to a single variant via the
    registry's type-based dispatch (most-specific-wins). The base
    `supports()` returns `True` only for the concrete variant the
    renderer was registered against, so the registry handles dispatch.

    Subclass and override `render`. If a subclass supports multiple
    `Finding` variants, override `supports()` to declare which.
    """

    @abstractmethod
    def render(self, finding: Finding, format: str = "text") -> str:
        """Render `finding` to a string in the given format.

        Args:
            finding: Any object satisfying the `Finding` Protocol.
            format: Output format. At minimum, implementations support
                `"text"` (plain) and `"markdown"`. Unknown formats
                should raise `ValueError`.

        Returns:
            A string suitable for direct emission to a terminal,
            markdown file, log line, etc. — depending on `format`.
        """

    def supports(self, finding_type: type) -> bool:
        """Whether this renderer accepts findings of `finding_type`.

        Default: returns `False`; subclasses or the registry pin
        renderers to a specific variant. The registry uses this only
        as a fallback — primary dispatch is by isinstance-against-the-
        registered-type, not by calling `supports()`.
        """
        del finding_type
        return False
