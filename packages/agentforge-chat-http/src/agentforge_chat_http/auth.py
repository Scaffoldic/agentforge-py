"""Bearer auth for `agentforge-chat-http`.

feat-020 v0.2 shipped its own `BearerAuthPolicy` ABC + `Principal`
+ `EnvBearerAuth` here. feat-014 lifted those into canonical
contracts in `agentforge-core` and a concrete implementation in
`agentforge`. This module now re-exports the canonical symbols
for backward compatibility:

    BearerAuthPolicy  — alias for `agentforge_core.contracts.auth.AuthPolicy`
    Principal         — alias for `agentforge_core.values.auth.Principal`
    EnvBearerAuth     — re-export from `agentforge.auth`
"""

from __future__ import annotations

from agentforge.auth import EnvBearerAuth
from agentforge_core.contracts.auth import AuthPolicy
from agentforge_core.values.auth import Principal

BearerAuthPolicy = AuthPolicy
"""Backward-compatible alias for v0.2 consumers. New code should
import `AuthPolicy` from `agentforge_core.contracts.auth`."""


__all__ = [
    "AuthPolicy",
    "BearerAuthPolicy",
    "EnvBearerAuth",
    "Principal",
]
