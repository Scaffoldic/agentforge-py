"""Pytest fixtures for `agentforge-voyage` unit tests."""

from __future__ import annotations

import pytest
from agentforge_voyage import VoyageEmbeddingClient
from agentforge_voyage._inmem_runner import FakeVoyageRunner


@pytest.fixture
def fake_runner() -> FakeVoyageRunner:
    return FakeVoyageRunner()


@pytest.fixture
def client(fake_runner: FakeVoyageRunner) -> VoyageEmbeddingClient:
    return VoyageEmbeddingClient(runner=fake_runner, model="voyage-3-large")
