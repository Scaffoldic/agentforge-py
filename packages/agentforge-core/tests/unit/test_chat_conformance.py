"""Chat conformance harness — exercises (feat-020).

Uses an inline simple in-memory store to validate the harness
itself behaves. The shipped `InMemoryChatHistory` in
`agentforge-chat` runs the same harness in chunk 2.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

import pytest
from agentforge_core.contracts.chat import ChatHistoryStore, HistoryTruncationStrategy
from agentforge_core.testing import (
    run_chat_history_conformance,
    run_truncation_conformance,
)
from agentforge_core.values.chat import ChatTurn, SessionInfo


class _DictHistory(ChatHistoryStore):
    """Tiny dict-backed in-memory store used only to exercise the
    conformance harness."""

    def __init__(self) -> None:
        self._turns: list[ChatTurn] = []
        self._meta: dict[str, dict[str, Any]] = {}
        self._owners: dict[str, str | None] = {}

    async def append(self, turn: ChatTurn) -> None:
        self._turns.append(turn)

    async def load(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        roles: list[str] | None = None,
    ) -> list[ChatTurn]:
        out = [t for t in self._turns if t.session_id == session_id]
        if before is not None:
            out = [t for t in out if t.timestamp < before]
        if after is not None:
            out = [t for t in out if t.timestamp > after]
        if roles is not None:
            out = [t for t in out if t.role in roles]
        out.sort(key=lambda t: t.timestamp)
        if limit is not None:
            out = out[:limit]
        return out

    async def count(self, session_id: str) -> int:
        return sum(1 for t in self._turns if t.session_id == session_id)

    async def delete_session(self, session_id: str) -> int:
        removed = sum(1 for t in self._turns if t.session_id == session_id)
        self._turns = [t for t in self._turns if t.session_id != session_id]
        self._meta.pop(session_id, None)
        self._owners.pop(session_id, None)
        return removed

    async def list_sessions(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[SessionInfo]:
        # Include metadata-only sessions (created before their first
        # turn — bug-018), not just sessions that have turns.
        ids = {t.session_id for t in self._turns} | set(self._meta)
        out: list[SessionInfo] = []
        for sid in ids:
            o = self._owners.get(sid)
            if owner is not None and o != owner:
                continue
            out.append(
                SessionInfo(
                    id=sid,
                    owner=o,
                    metadata=self._meta.get(sid, {}),
                    turn_count=sum(1 for t in self._turns if t.session_id == sid),
                )
            )
        if before is not None:
            out = [s for s in out if s.last_active_at < before]
        return out[:limit]

    async def update_session_metadata(self, session_id: str, metadata: Mapping[str, Any]) -> None:
        bag = self._meta.setdefault(session_id, {})
        for k, v in metadata.items():
            bag[k] = v
        if "owner" in metadata:
            self._owners[session_id] = metadata["owner"]

    async def expire_before(self, cutoff: datetime) -> int:
        del cutoff
        return 0  # no TTL

    async def close(self) -> None:
        return None


class _Keep2(HistoryTruncationStrategy):
    async def select(
        self,
        all_turns: list[ChatTurn],
        next_user_message: str,
        context: Mapping[str, Any],
    ) -> list[ChatTurn]:
        del next_user_message, context
        return all_turns[-2:]


@pytest.mark.asyncio
async def test_chat_history_conformance_passes_on_dict_store() -> None:
    await run_chat_history_conformance(_DictHistory())


@pytest.mark.asyncio
async def test_truncation_conformance_passes_on_simple_strategy() -> None:
    await run_truncation_conformance(_Keep2())
