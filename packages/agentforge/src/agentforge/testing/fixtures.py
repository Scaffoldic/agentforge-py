"""Pytest fixtures (feat-016).

Importing this module registers the fixtures into the active
session via `pytest.fixture` — typical usage is to re-export the
two fixtures from a project's `conftest.py`:

    # tests/conftest.py
    from agentforge.testing.fixtures import mock_llm, temp_memory_store

The fixtures are framework-agnostic in spirit but the decorator is
pytest-specific. Other test runners can construct the helpers
themselves via `MockLLMClient.deterministic(...)` and
`InMemoryStore()` directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from agentforge.memory import InMemoryStore
from agentforge.testing.llm import MockLLMClient


@pytest.fixture
def mock_llm() -> MockLLMClient:
    """A fresh `MockLLMClient.deterministic("ok")` per test."""
    return MockLLMClient.deterministic("ok")


@pytest.fixture
async def temp_memory_store() -> AsyncIterator[InMemoryStore]:
    """An `InMemoryStore` that's cleared after the test."""
    store = InMemoryStore()
    try:
        yield store
    finally:
        await store.close()


__all__ = ["mock_llm", "temp_memory_store"]
