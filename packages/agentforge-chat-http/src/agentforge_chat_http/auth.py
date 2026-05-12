"""Bearer auth for `agentforge-chat-http` (feat-020 v0.2 scope).

`BearerAuthPolicy` is a minimal placeholder ABC; when feat-014's
real `AuthPolicy` contract lands in `agentforge-core`, this becomes
a thin adapter and is documented as such.

`EnvBearerAuth(token_env_var="API_TOKENS")` reads a
comma-separated list of valid bearer tokens from an environment
variable; each token maps to an opaque principal id (the token
itself by default).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    """Identity returned by a successful `authenticate(...)` call."""

    id: str
    metadata: dict[str, str] | None = None


class BearerAuthPolicy(ABC):
    """Per-feat-020 v0.2 placeholder. Refactor to feat-014's
    `AuthPolicy` when that ships."""

    @abstractmethod
    async def authenticate(self, bearer_token: str | None) -> Principal | None:
        """Return a `Principal` if the token is valid, else None."""


class EnvBearerAuth(BearerAuthPolicy):
    """Bearer-token policy backed by a comma-separated env var.

    Format of ``$<token_env_var>``: ``"token1,token2,token3"``.
    Each token is its own principal id (no token → identity map).
    """

    def __init__(self, token_env_var: str = "API_TOKENS") -> None:  # noqa: S107  # nosec B107 — env-var NAME, not a token
        self._var = token_env_var

    async def authenticate(self, bearer_token: str | None) -> Principal | None:
        if bearer_token is None or not bearer_token:
            return None
        raw = os.environ.get(self._var, "")
        if not raw:
            return None
        valid = {t.strip() for t in raw.split(",") if t.strip()}
        if bearer_token in valid:
            return Principal(id=bearer_token)
        return None


__all__ = [
    "BearerAuthPolicy",
    "EnvBearerAuth",
    "Principal",
]
