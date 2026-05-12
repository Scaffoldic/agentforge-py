"""Unit tests for chat contracts (feat-020)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from agentforge_core.contracts.chat import ChatHistoryStore, HistoryTruncationStrategy
from agentforge_core.values.chat import ChatTurn, SessionInfo


def test_chat_history_store_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError, match="abstract"):
        ChatHistoryStore()  # type: ignore[abstract]


def test_truncation_strategy_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError, match="abstract"):
        HistoryTruncationStrategy()  # type: ignore[abstract]


class _StubHistory(ChatHistoryStore):
    async def append(self, turn: ChatTurn) -> None:
        return None

    async def load(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        roles: list[str] | None = None,
    ) -> list[ChatTurn]:
        del session_id, limit, before, after, roles
        return []

    async def count(self, session_id: str) -> int:
        del session_id
        return 0

    async def delete_session(self, session_id: str) -> int:
        del session_id
        return 0

    async def list_sessions(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[SessionInfo]:
        del owner, limit, before
        return []

    async def update_session_metadata(self, session_id: str, metadata: Mapping[str, Any]) -> None:
        del session_id, metadata

    async def expire_before(self, cutoff: datetime) -> int:
        del cutoff
        return 0

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_stub_history_satisfies_contract() -> None:
    store = _StubHistory()
    assert isinstance(store, ChatHistoryStore)
    await store.append(
        ChatTurn(id="x", session_id="s", role="user", content="hi", timestamp=datetime.now(UTC))
    )
    assert await store.count("s") == 0
    assert store.capabilities() == set()
    assert store.supports("ttl") is False


class _NoOpTruncation(HistoryTruncationStrategy):
    async def select(
        self,
        all_turns: list[ChatTurn],
        next_user_message: str,
        context: Mapping[str, Any],
    ) -> list[ChatTurn]:
        del next_user_message, context
        return list(all_turns)


@pytest.mark.asyncio
async def test_stub_truncation_works() -> None:
    s = _NoOpTruncation()
    turns = [ChatTurn(id=str(i), session_id="s", role="user", content=str(i)) for i in range(3)]
    out = await s.select(turns, "next", {})
    assert out == turns
