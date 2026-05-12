"""Unit tests for `AuthPolicy` (feat-014)."""

from __future__ import annotations

import pytest
from agentforge_core.contracts.auth import AuthPolicy
from agentforge_core.values.auth import Principal


def test_auth_policy_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError, match="abstract"):
        AuthPolicy()  # type: ignore[abstract]


class _NullAuth(AuthPolicy):
    async def authenticate(self, bearer_token: str | None) -> Principal | None:
        if bearer_token == "good":
            return Principal(id="user-good")
        return None


@pytest.mark.asyncio
async def test_minimal_subclass_works() -> None:
    auth = _NullAuth()
    assert (await auth.authenticate("good")) == Principal(id="user-good")
    assert (await auth.authenticate("bad")) is None
    assert (await auth.authenticate(None)) is None
