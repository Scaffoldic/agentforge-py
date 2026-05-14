"""Pytest fixtures for `agentforge-anthropic` unit tests."""

from __future__ import annotations

import pytest
from agentforge_anthropic import AnthropicClient
from agentforge_anthropic._inmem_runner import FakeAnthropicRunner


@pytest.fixture
def fake_runner() -> FakeAnthropicRunner:
    return FakeAnthropicRunner()


@pytest.fixture
def client(fake_runner: FakeAnthropicRunner) -> AnthropicClient:
    return AnthropicClient(runner=fake_runner, model_id="claude-sonnet-4-7")
