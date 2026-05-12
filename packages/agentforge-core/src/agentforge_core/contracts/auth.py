"""`AuthPolicy` — locked authentication contract (feat-014).

Both `agentforge-chat-http` (feat-020) and `agentforge-a2a`
(feat-014) need to validate incoming bearer tokens against
configured credentials. This contract unifies them.

Server-side validation only: `authenticate(bearer_token) ->
Principal | None`. Client-side credential attachment is
dict-driven (per-peer config carries `{type, token, cert,
key, ...}`) — no policy abstraction; outgoing transports build
the right httpx parameters from the dict.

Per ADR-0007 the methods on this ABC are locked once the
feature ships. Adding a method is a major-version bump.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentforge_core.values.auth import Principal


class AuthPolicy(ABC):
    """Validates incoming bearer credentials against configured
    identities. Implementations are typically env-backed
    (`EnvBearerAuth`) or registry-backed."""

    @abstractmethod
    async def authenticate(self, bearer_token: str | None) -> Principal | None:
        """Return a `Principal` when the token is valid, else
        ``None``. ``None`` input (missing header) must yield
        ``None``."""
