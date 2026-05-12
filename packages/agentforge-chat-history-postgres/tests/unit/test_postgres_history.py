"""Unit tests for `PostgresChatHistory` against the fake runner."""

from __future__ import annotations

import pytest
from agentforge_chat_history_postgres import PostgresChatHistory
from agentforge_chat_history_postgres._inmem_runner import PostgresFakeRunner
from agentforge_core.testing import run_chat_history_conformance


@pytest.mark.asyncio
async def test_postgres_chat_history_satisfies_conformance() -> None:
    runner = PostgresFakeRunner()
    store = await PostgresChatHistory.from_dsn("postgres://fake", runner=runner)
    await run_chat_history_conformance(store)
    await store.close()
    assert runner.closed is True


@pytest.mark.asyncio
async def test_postgres_chat_history_capabilities() -> None:
    runner = PostgresFakeRunner()
    store = await PostgresChatHistory.from_dsn("postgres://fake", runner=runner)
    caps = store.capabilities()
    assert "ttl" in caps
    assert "encryption_at_rest" in caps
    assert "full_text_search" in caps
    await store.close()
