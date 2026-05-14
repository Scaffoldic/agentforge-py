"""Pytest fixtures for `agentforge-ollama` unit tests."""

from __future__ import annotations

import pytest
from agentforge_ollama import OllamaClient, OllamaEmbeddingClient
from agentforge_ollama._inmem_runner import FakeOllamaRunner


@pytest.fixture
def fake_runner() -> FakeOllamaRunner:
    return FakeOllamaRunner()


@pytest.fixture
def client(fake_runner: FakeOllamaRunner) -> OllamaClient:
    return OllamaClient(runner=fake_runner, model_id="llama3.2:3b")


@pytest.fixture
def embedding_client(fake_runner: FakeOllamaRunner) -> OllamaEmbeddingClient:
    return OllamaEmbeddingClient(
        runner=fake_runner,
        model="mxbai-embed-large",
        dimensions=1024,
    )
