"""Concrete `AuthPolicy` implementations shipped with the framework
(feat-014).

`EnvBearerAuth(token_env_var)` reads a comma-separated list of
valid bearer tokens from an environment variable; each token
maps to a `Principal` whose id is the token itself. Suitable for
small/internal deployments; production deployments typically
implement their own `AuthPolicy` against a real identity
provider.
"""

from __future__ import annotations

import os

from agentforge_core.contracts.auth import AuthPolicy
from agentforge_core.values.auth import Principal


class EnvBearerAuth(AuthPolicy):
    """Bearer-token policy backed by a comma-separated env var.

    Format of ``$<token_env_var>``: ``"token1,token2,token3"``.
    Each token is its own principal id (no token → identity map).
    """

    def __init__(self, token_env_var: str = "API_TOKENS") -> None:  # noqa: S107  # nosec B107 — env-var NAME
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


__all__ = ["EnvBearerAuth"]
