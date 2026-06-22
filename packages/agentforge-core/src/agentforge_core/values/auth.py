"""Auth value types (feat-014; widened by feat-029).

`Principal` is the identity carried through the framework — returned by an
`AuthPolicy` after a successful authentication (feat-014) and issued /
resolved by an `IdentityProvider` (feat-029, governance identity). It
carries an opaque ``id`` (the token itself by default; a stable URN once a
real identity provider is wired — e.g.
``agentforge:agent:<org>/<name>@<version>``) plus optional ``kind`` /
``owner`` and a free-form ``metadata`` attribute bag (role tags, tenant
id, env, region, …).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    """Identity returned by `AuthPolicy.authenticate(...)` and issued /
    resolved by `IdentityProvider` (feat-029).

    Attributes:
        id: Stable identifier — a bearer token for env-backed auth, or a
            URN for a governance identity provider.
        kind: What the principal *is* — ``"agent"`` (default), ``"tool"``,
            ``"service"``, or ``"human"``.
        owner: The team / human accountable for the principal, if known.
        metadata: Free-form string attributes (env, region, role tags,
            tenant id) — the governance ``attributes`` bag.
    """

    id: str
    kind: str = "agent"
    owner: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
