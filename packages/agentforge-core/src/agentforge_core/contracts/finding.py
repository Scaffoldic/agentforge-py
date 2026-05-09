"""`Finding` — structural Protocol the agent's output items satisfy.

Per feat-008 / ADR-0012, `Finding` is a `runtime_checkable` Protocol
rather than a single dataclass. Shipped variants (`SimpleFinding`,
`PatchFinding`, `NarrativeFinding`, `MultiSpanFinding`) live in the
runtime package; they satisfy this Protocol structurally without
needing to inherit from anything.

Custom variants from agent code or third-party packages also satisfy
the Protocol simply by declaring the required attributes — no
registration ceremony.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Finding(Protocol):
    """Minimum shape any pipeline / agent output item satisfies.

    The runtime checks `isinstance(x, Finding)` opportunistically (e.g.
    when storing as a `Claim.payload`); the check is structural and
    tolerant.
    """

    severity: str
    """One of "critical" | "warning" | "suggestion" | "info"."""

    category: str
    """Free-form categorisation: "style", "security", "answer", etc."""

    message: str
    """Short human-readable summary (one or two sentences)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict for persistence / transport."""
        ...
