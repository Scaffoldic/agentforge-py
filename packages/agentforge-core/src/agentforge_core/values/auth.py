"""Auth value types (feat-014).

`Principal` is the identity returned by an `AuthPolicy` after a
successful authentication. Carries an opaque ``id`` (the token
itself by default; an opaque user id once a real identity
provider is wired) plus optional metadata for downstream use
(role tags, tenant id, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    """Identity returned by `AuthPolicy.authenticate(...)`."""

    id: str
    metadata: dict[str, str] = field(default_factory=dict)
