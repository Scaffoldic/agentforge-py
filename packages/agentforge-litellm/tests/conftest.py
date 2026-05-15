"""Pytest fixtures for `agentforge-litellm` unit tests."""

from __future__ import annotations

import pytest
from agentforge_litellm import LiteLLMClient
from agentforge_litellm._inmem_runner import FakeLiteLLMRunner


@pytest.fixture
def fake_runner() -> FakeLiteLLMRunner:
    return FakeLiteLLMRunner()


@pytest.fixture
def client(fake_runner: FakeLiteLLMRunner) -> LiteLLMClient:
    return LiteLLMClient(runner=fake_runner, model_id="gpt-4o-mini")
