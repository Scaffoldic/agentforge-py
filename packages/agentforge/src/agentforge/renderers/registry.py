"""`RendererRegistry` — isinstance-based dispatch for `FindingRenderer`s.

Registration maps a `Finding` (sub)type to a renderer. Lookup walks
the registrations and returns the renderer whose registered type is
the **most specific** (most-derived) ancestor of the finding's type.

Ties broken by registration order (first wins) — predictable and
documented. The most-specific rule matches the spec's intent for
custom variants subclassing a shipped variant: registering a renderer
for the subclass overrides the parent renderer.
"""

from __future__ import annotations

from agentforge_core.contracts.finding import Finding
from agentforge_core.contracts.renderer import FindingRenderer


class MissingRendererError(LookupError):
    """Raised by `RendererRegistry.get` when no renderer matches."""


class RendererRegistry:
    """Map `Finding` (sub)types to `FindingRenderer`s.

    Use `register(finding_type, renderer)` to add an entry. Use
    `get(finding)` to dispatch — returns the most-specific match.
    `default()` returns a registry pre-populated with the four
    built-in renderers shipped for the standard variants.
    """

    def __init__(self) -> None:
        # List preserves registration order; `dict[type, renderer]`
        # would lose duplicates and registration order is part of the
        # tie-break rule.
        self._registrations: list[tuple[type, FindingRenderer]] = []

    def register(self, finding_type: type, renderer: FindingRenderer) -> None:
        """Register `renderer` for findings of type `finding_type` or
        any subclass.

        Re-registering the same exact type replaces the prior
        registration in place (preserves the original registration
        order).
        """
        for idx, (existing_type, _) in enumerate(self._registrations):
            if existing_type is finding_type:
                self._registrations[idx] = (finding_type, renderer)
                return
        self._registrations.append((finding_type, renderer))

    def get(self, finding: Finding) -> FindingRenderer:
        """Look up the most-specific renderer for `finding`.

        Iterates registrations and selects the one whose registered
        type is the most-derived ancestor of `type(finding)`. Ties
        are broken by registration order (first wins).

        Raises:
            MissingRendererError: if no registered type matches.
        """
        best: tuple[type, FindingRenderer] | None = None
        finding_type = type(finding)
        for registered_type, renderer in self._registrations:
            if not isinstance(finding, registered_type):
                continue
            if best is None or _is_more_specific(registered_type, best[0], finding_type):
                best = (registered_type, renderer)
        if best is None:
            raise MissingRendererError(
                f"No renderer registered for {finding_type.__name__!r}. "
                f"Use RendererRegistry.register({finding_type.__name__}, …) or call "
                f"RendererRegistry.default() to get a pre-populated registry."
            )
        return best[1]

    def registered_types(self) -> tuple[type, ...]:
        """Diagnostic: types currently registered, in registration order."""
        return tuple(t for t, _ in self._registrations)


def _is_more_specific(candidate: type, current_best: type, target: type) -> bool:
    """Is `candidate` a more-specific ancestor of `target` than
    `current_best`? Both `candidate` and `current_best` are guaranteed
    to be ancestors of `target` at this point.

    "More specific" means: candidate is a proper subclass of
    current_best. If candidate == current_best, that's a tie — the
    first registration wins, so we report False (not strictly more
    specific).
    """
    del target  # only relied on by callers for the ancestor invariant
    return candidate is not current_best and issubclass(candidate, current_best)
