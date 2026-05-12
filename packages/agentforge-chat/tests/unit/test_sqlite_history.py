"""Unit tests for `SqliteChatHistory`."""

from __future__ import annotations

import pytest
from agentforge_chat import SqliteChatHistory
from agentforge_core.testing import run_chat_history_conformance


@pytest.mark.asyncio
async def test_sqlite_history_passes_conformance() -> None:
    async with await SqliteChatHistory.from_path(":memory:") as store:
        await run_chat_history_conformance(store)
