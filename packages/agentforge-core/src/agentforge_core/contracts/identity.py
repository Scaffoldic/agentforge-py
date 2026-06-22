"""`IdentityProvider` — locked governance-identity contract (feat-029).

Every agent (and the tools / services it speaks to) gets a stable, portable
`Principal` so every action has a name. A provider:

- **issues** a principal for an agent from its declared name + owner,
- **resolves** a principal by id,
- **verifies** an inbound credential into a principal (prove who's calling),
- mints an outbound **credential** for a principal (prove who we are),
- **rotates** a principal's credential.

Per ADR-0007 the methods on this ABC are locked once the feature ships;
adding a method is a major-version bump. Optional behaviour goes behind
`capabilities()` / `supports()`.

The contract is vendor-neutral by construction: the `local` driver is
self-contained and offline (deterministic, no network); OIDC / SPIFFE /
cloud-IAM drivers map onto the same surface without the framework taking a
hard dependency on any of them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from agentforge_core.values.auth import Principal


class IdentityError(ValueError):
    """Raised when a credential cannot be verified into a principal, or a
    principal cannot be resolved for an operation that requires one."""


class IdentityProvider(ABC):
    """Issues, resolves, verifies, and rotates `Principal` identities."""

    @abstractmethod
    async def issue(
        self,
        *,
        name: str,
        owner: str,
        attributes: Mapping[str, str] | None = None,
    ) -> Principal:
        """Mint (or return the existing) principal for an agent.

        `name` is the agent's logical name; `owner` the accountable team /
        human; `attributes` free-form string tags (env, region, …). The
        returned `Principal.id` is stable across calls for the same
        `name` (idempotent issue)."""

    @abstractmethod
    async def resolve(self, principal_id: str) -> Principal | None:
        """Return the principal with this id, or ``None`` if unknown."""

    @abstractmethod
    async def verify(self, token: str) -> Principal:
        """Verify an inbound credential and return its principal.

        Raises:
            IdentityError: the token is missing, malformed, expired, or
                not issued by this provider.
        """

    @abstractmethod
    async def credential(self, principal: Principal) -> str:
        """Mint an outbound credential (token / assertion) that another
        party can `verify()` back into `principal`."""

    @abstractmethod
    async def rotate(self, principal_id: str) -> Principal:
        """Rotate the principal's signing material / credential. The
        principal id is unchanged; previously minted credentials stop
        verifying.

        Raises:
            IdentityError: `principal_id` is unknown.
        """

    def capabilities(self) -> set[str]:
        """Optional capabilities this provider honours, from a closed
        vocabulary (e.g. ``"rotation"``, ``"oidc"``, ``"spiffe"``).
        Default: none."""
        return set()

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities()
