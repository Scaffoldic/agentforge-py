"""Unit tests for `EnvBearerAuth` (feat-014)."""

from __future__ import annotations

import pytest
from agentforge import EnvBearerAuth
from agentforge_core.values.auth import Principal


@pytest.mark.asyncio
async def test_valid_token_returns_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKENS", "alpha,beta")
    auth = EnvBearerAuth("API_TOKENS")
    p = await auth.authenticate("alpha")
    assert p == Principal(id="alpha")


@pytest.mark.asyncio
async def test_invalid_token_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKENS", "alpha")
    assert (await EnvBearerAuth("API_TOKENS").authenticate("beta")) is None


@pytest.mark.asyncio
async def test_none_token_returns_none() -> None:
    assert (await EnvBearerAuth("ANY").authenticate(None)) is None


@pytest.mark.asyncio
async def test_missing_env_var_rejects_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_VAR_XYZ", raising=False)
    assert (await EnvBearerAuth("MISSING_VAR_XYZ").authenticate("anything")) is None


@pytest.mark.asyncio
async def test_empty_env_var_rejects_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKENS", "")
    assert (await EnvBearerAuth("API_TOKENS").authenticate("anything")) is None
