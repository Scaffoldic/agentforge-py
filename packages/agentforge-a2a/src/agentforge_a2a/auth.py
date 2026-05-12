"""Client-side credential providers for A2A (feat-014).

`agent_call` resolves per-peer auth config to one of the two
built-in `ClientAuth` shapes:

- `BearerAuth(token)` — attaches ``Authorization: Bearer
  <token>`` to outgoing requests.
- `MutualTLSAuth(cert_path, key_path)` — builds an
  `ssl.SSLContext` the httpx client passes to the peer.

`build_outgoing_auth(config)` accepts the dict form found in
YAML (`{type: bearer, token: ...}` / `{type: mtls, cert: ...,
key: ...}`) and returns the corresponding `ClientAuth`.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentforge_core.production.exceptions import ModuleError


@dataclass(frozen=True)
class ClientAuth:
    """Resolved client-side credentials for an A2A peer.

    `headers` is merged into the outgoing request headers;
    `ssl_context` is passed to the httpx client when present.
    """

    headers: dict[str, str] = field(default_factory=dict)
    ssl_context: ssl.SSLContext | None = None


def BearerAuth(token: str) -> ClientAuth:  # noqa: N802 — factory-named like a class
    """Bearer-token credentials. Returns a `ClientAuth` ready to
    use with `agent_call`."""
    return ClientAuth(headers={"Authorization": f"Bearer {token}"})


def MutualTLSAuth(  # noqa: N802 — factory-named like a class
    cert_path: str | Path,
    key_path: str | Path,
    *,
    ca_path: str | Path | None = None,
) -> ClientAuth:
    """mTLS credentials. Builds an `ssl.SSLContext` loading the
    client cert + key (and an optional CA bundle)."""
    ctx = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH,
        cafile=str(ca_path) if ca_path is not None else None,
    )
    ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return ClientAuth(ssl_context=ctx)


def build_outgoing_auth(config: dict[str, Any]) -> ClientAuth:
    """Resolve a per-peer auth dict to a `ClientAuth`.

    Accepted shapes:
      - ``{}`` — no auth.
      - ``{type: "bearer", token: "..."}``.
      - ``{type: "mtls", cert: "/path", key: "/path",
            ca: "/path" (optional)}``.
    """
    if not config:
        return ClientAuth()
    auth_type = config.get("type", "")
    if auth_type == "bearer":
        token = config.get("token", "")
        if not token:
            raise ModuleError("bearer auth requires a non-empty 'token'")
        return BearerAuth(token)
    if auth_type == "mtls":
        cert = config.get("cert", "")
        key = config.get("key", "")
        ca = config.get("ca")
        if not cert or not key:
            raise ModuleError("mtls auth requires both 'cert' and 'key' paths")
        return MutualTLSAuth(cert, key, ca_path=ca)
    raise ModuleError(f"unknown a2a auth type: {auth_type!r}")


__all__ = [
    "BearerAuth",
    "ClientAuth",
    "MutualTLSAuth",
    "build_outgoing_auth",
]
