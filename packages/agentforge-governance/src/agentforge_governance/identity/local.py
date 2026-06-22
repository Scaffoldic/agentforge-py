"""`LocalIdentityProvider` — offline, self-contained identity (feat-029).

The zero-ops default driver: issues, resolves, and verifies `Principal`s
entirely in-process with HMAC-signed credentials — no network, no cloud
account, deterministic for tests. The analogue of the SQLite `MemoryStore`
for the identity pillar.

Principal ids use the stable URN scheme
``agentforge:agent:<org>/<name>@<version>`` so they are portable and a
later OIDC / SPIFFE / cloud-IAM driver can map onto the same shape.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Mapping

from agentforge_core.contracts.identity import IdentityError, IdentityProvider
from agentforge_core.values.auth import Principal

_SEP = "~"  # credential = "<principal-id>~<hmac-hex>"; absent from the URN charset


class LocalIdentityProvider(IdentityProvider):
    """In-process identity provider with HMAC-signed credentials."""

    def __init__(self, *, org: str = "local", version: str = "1") -> None:
        self._org = org
        self._version = version
        self._principals: dict[str, Principal] = {}
        self._secrets: dict[str, str] = {}

    @classmethod
    async def from_config(cls, *, org: str = "local", version: str = "1") -> LocalIdentityProvider:
        return cls(org=org, version=version)

    def _urn(self, name: str) -> str:
        return f"agentforge:agent:{self._org}/{name}@{self._version}"

    @staticmethod
    def _mac(principal_id: str, secret: str) -> str:
        return hmac.new(secret.encode(), principal_id.encode(), hashlib.sha256).hexdigest()

    async def issue(
        self,
        *,
        name: str,
        owner: str,
        attributes: Mapping[str, str] | None = None,
    ) -> Principal:
        principal_id = self._urn(name)
        existing = self._principals.get(principal_id)
        if existing is not None:
            return existing  # idempotent on name
        principal = Principal(
            id=principal_id,
            kind="agent",
            owner=owner,
            metadata=dict(attributes or {}),
        )
        self._principals[principal_id] = principal
        self._secrets[principal_id] = secrets.token_hex(16)
        return principal

    async def resolve(self, principal_id: str) -> Principal | None:
        return self._principals.get(principal_id)

    async def credential(self, principal: Principal) -> str:
        secret = self._secrets.get(principal.id)
        if secret is None:
            msg = f"credential: unknown principal {principal.id!r}; issue it first"
            raise IdentityError(msg)
        return f"{principal.id}{_SEP}{self._mac(principal.id, secret)}"

    async def verify(self, token: str) -> Principal:
        principal_id, sep, signature = token.rpartition(_SEP)
        if not sep:
            raise IdentityError("verify: malformed credential")
        secret = self._secrets.get(principal_id)
        principal = self._principals.get(principal_id)
        if secret is None or principal is None:
            raise IdentityError("verify: unknown or revoked principal")
        if not hmac.compare_digest(signature, self._mac(principal_id, secret)):
            raise IdentityError("verify: credential signature mismatch")
        return principal

    async def rotate(self, principal_id: str) -> Principal:
        principal = self._principals.get(principal_id)
        if principal is None:
            raise IdentityError(f"rotate: unknown principal {principal_id!r}")
        self._secrets[principal_id] = secrets.token_hex(16)  # invalidates prior credentials
        return principal

    def capabilities(self) -> set[str]:
        return {"rotation"}


__all__ = ["LocalIdentityProvider"]
