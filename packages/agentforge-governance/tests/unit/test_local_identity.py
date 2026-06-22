"""Unit + conformance tests for `LocalIdentityProvider` (feat-029)."""

from __future__ import annotations

import pytest
from agentforge.cli._build import build_identity_from_config
from agentforge_core.config.schema import AgentForgeConfig
from agentforge_core.contracts.identity import IdentityError
from agentforge_core.testing import run_identity_conformance
from agentforge_core.values.auth import Principal
from agentforge_governance import LocalIdentityProvider


@pytest.mark.asyncio
async def test_identity_conformance() -> None:
    provider = await LocalIdentityProvider.from_config(org="finance")
    await run_identity_conformance(provider)


@pytest.mark.asyncio
async def test_urn_scheme_and_idempotent_issue() -> None:
    idp = LocalIdentityProvider(org="acme", version="2")
    p = await idp.issue(name="reconciler", owner="platform", attributes={"env": "prod"})
    assert p.id == "agentforge:agent:acme/reconciler@2"
    assert p.kind == "agent"
    assert p.owner == "platform"
    assert p.metadata == {"env": "prod"}
    again = await idp.issue(name="reconciler", owner="someone-else")
    assert again is p  # idempotent: same instance, owner not overwritten


@pytest.mark.asyncio
async def test_rotation_invalidates_old_credential() -> None:
    idp = LocalIdentityProvider()
    p = await idp.issue(name="a", owner="o")
    old = await idp.credential(p)
    await idp.rotate(p.id)
    with pytest.raises(IdentityError, match=r"signature mismatch|revoked"):
        await idp.verify(old)
    assert (await idp.verify(await idp.credential(p))).id == p.id


@pytest.mark.asyncio
async def test_credential_for_unknown_principal_raises() -> None:
    idp = LocalIdentityProvider()
    with pytest.raises(IdentityError, match="unknown principal"):
        await idp.credential(Principal(id="agentforge:agent:x/y@1"))


def test_capabilities() -> None:
    idp = LocalIdentityProvider()
    assert idp.capabilities() == {"rotation"}
    assert idp.supports("rotation")
    assert not idp.supports("oidc")


@pytest.mark.asyncio
async def test_build_identity_from_config() -> None:
    """The `governance.identity` block resolves the `local` driver via its
    entry point and issues the agent's principal."""
    cfg = AgentForgeConfig.model_validate(
        {
            "governance": {
                "identity": {
                    "provider": "local",
                    "name": "reconciler",
                    "owner": "finance",
                    "attributes": {"env": "prod"},
                }
            }
        }
    )
    provider = await build_identity_from_config(cfg)
    assert isinstance(provider, LocalIdentityProvider)
    issued = await provider.resolve("agentforge:agent:local/reconciler@1")
    assert issued is not None
    assert issued.owner == "finance"


def test_no_governance_block_is_valid_and_inert() -> None:
    cfg = AgentForgeConfig()
    assert cfg.governance.identity is None
