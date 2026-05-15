"""Pytest fixtures for `agentforge-openai` unit tests."""

from __future__ import annotations

import pytest
from agentforge_openai import OpenAIClient, OpenAIEmbeddingClient
from agentforge_openai._inmem_runner import FakeOpenAIRunner


@pytest.fixture
def fake_runner() -> FakeOpenAIRunner:
    return FakeOpenAIRunner()


@pytest.fixture
def client(fake_runner: FakeOpenAIRunner) -> OpenAIClient:
    return OpenAIClient(runner=fake_runner, model_id="gpt-4o-mini")


@pytest.fixture
def embedding_client(fake_runner: FakeOpenAIRunner) -> OpenAIEmbeddingClient:
    return OpenAIEmbeddingClient(runner=fake_runner, model="text-embedding-3-small")
