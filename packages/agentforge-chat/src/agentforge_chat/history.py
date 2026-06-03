"""`InMemoryChatHistory` — process-local default `ChatHistoryStore`.

Backs `ChatSession` when no driver is configured. Useful for tests
and tiny demos; not persistent across process restarts.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from agentforge_core.contracts.chat import ChatHistoryStore
from agentforge_core.values.chat import ChatTurn, SessionInfo


class InMemoryChatHistory(ChatHistoryStore):
    """Thread-safe in-memory implementation of `ChatHistoryStore`."""

    def __init__(self) -> None:
        self._turns: dict[str, list[ChatTurn]] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        self._owners: dict[str, str | None] = {}
        self._created_at: dict[str, datetime] = {}
        self._last_active: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def append(self, turn: ChatTurn) -> None:
        async with self._lock:
            self._turns.setdefault(turn.session_id, []).append(turn)
            now = datetime.now(UTC)
            self._created_at.setdefault(turn.session_id, now)
            self._last_active[turn.session_id] = now

    async def load(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        roles: list[str] | None = None,
    ) -> list[ChatTurn]:
        async with self._lock:
            turns = list(self._turns.get(session_id, []))
        if before is not None:
            turns = [t for t in turns if t.timestamp < before]
        if after is not None:
            turns = [t for t in turns if t.timestamp > after]
        if roles is not None:
            allowed = set(roles)
            turns = [t for t in turns if t.role in allowed]
        turns.sort(key=lambda t: t.timestamp)
        if limit is not None:
            turns = turns[:limit]
        return turns

    async def count(self, session_id: str) -> int:
        async with self._lock:
            return len(self._turns.get(session_id, []))

    async def delete_session(self, session_id: str) -> int:
        async with self._lock:
            removed = len(self._turns.pop(session_id, []))
            self._meta.pop(session_id, None)
            self._owners.pop(session_id, None)
            self._created_at.pop(session_id, None)
            self._last_active.pop(session_id, None)
            return removed

    async def list_sessions(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[SessionInfo]:
        async with self._lock:
            # Include sessions that exist only via metadata (created before
            # their first turn — bug-018), not just sessions with turns.
            sids = set(self._turns) | set(self._meta)
            out = [self._build_info(sid) for sid in sids]
        if owner is not None:
            out = [s for s in out if s.owner == owner]
        if before is not None:
            out = [s for s in out if s.last_active_at < before]
        out.sort(key=lambda s: s.last_active_at, reverse=True)
        return out[:limit]

    async def update_session_metadata(self, session_id: str, metadata: Mapping[str, Any]) -> None:
        async with self._lock:
            bag = self._meta.setdefault(session_id, {})
            for k, v in metadata.items():
                bag[k] = v
            if "owner" in metadata:
                self._owners[session_id] = metadata["owner"]
            # Register timestamps so a metadata-only session (created before
            # its first turn — bug-018) carries sane created/last_active.
            now = datetime.now(UTC)
            self._created_at.setdefault(session_id, now)
            self._last_active.setdefault(session_id, now)

    async def expire_before(self, cutoff: datetime) -> int:
        async with self._lock:
            doomed = [sid for sid, last in self._last_active.items() if last < cutoff]
            for sid in doomed:
                self._turns.pop(sid, None)
                self._meta.pop(sid, None)
                self._owners.pop(sid, None)
                self._created_at.pop(sid, None)
                self._last_active.pop(sid, None)
            return len(doomed)

    async def close(self) -> None:
        return None

    def capabilities(self) -> set[str]:
        return {"ttl"}

    def _build_info(self, sid: str) -> SessionInfo:
        turns = self._turns.get(sid, [])
        return SessionInfo(
            id=sid,
            owner=self._owners.get(sid),
            created_at=self._created_at.get(sid, datetime.now(UTC)),
            last_active_at=self._last_active.get(sid, datetime.now(UTC)),
            turn_count=len(turns),
            total_cost_usd=sum(t.cost_usd for t in turns),
            metadata=dict(self._meta.get(sid, {})),
        )


__all__ = ["InMemoryChatHistory"]
