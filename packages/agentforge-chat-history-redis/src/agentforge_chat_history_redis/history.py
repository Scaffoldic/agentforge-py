"""`RedisChatHistory` — `ChatHistoryStore` over Redis via redis-py async.

Key layout:

- `chat:turn:<turn_id>` — hash of turn fields (role, content, JSON
  blobs for tool_calls / metadata).
- `chat:turns:<session_id>` — sorted set of turn IDs scored by
  timestamp (Unix epoch seconds; allows range queries on
  `before` / `after`).
- `chat:session:<session_id>` — hash of session metadata (owner,
  created_at, last_active_at, metadata).
- `chat:session_ids` — set of all known session IDs (used by
  `list_sessions`).

Native TTL via Redis `EXPIRE` on the session-scoped keys.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from agentforge_core.contracts.chat import ChatHistoryStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.chat import ChatRole, ChatTurn, SessionInfo
from agentforge_core.values.messages import ToolCall

from agentforge_chat_history_redis._runner import RedisRunner

_ALLOWED_ROLES: tuple[ChatRole, ...] = ("user", "assistant", "system", "tool")

_TURN_KEY = "chat:turn:{}"
_TURNS_INDEX_KEY = "chat:turns:{}"
_SESSION_KEY = "chat:session:{}"
_SESSIONS_INDEX_KEY = "chat:session_ids"


class RedisChatHistory(ChatHistoryStore):
    """`ChatHistoryStore` backed by Redis."""

    def __init__(self, *, runner: RedisRunner, ttl_seconds: int | None = None) -> None:
        self._r = runner
        self._ttl_seconds = ttl_seconds

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        ttl_seconds: int | None = None,
        runner: RedisRunner | None = None,
    ) -> RedisChatHistory:
        """Connect to ``url`` and wrap the connection."""
        if runner is None:  # pragma: no cover — exercised via `-m live`
            runner = await _build_client_runner(url)
        return cls(runner=runner, ttl_seconds=ttl_seconds)

    async def close(self) -> None:
        await self._r.close()

    async def append(self, turn: ChatTurn) -> None:
        ts = turn.timestamp.timestamp()
        await self._r.hset(
            _TURN_KEY.format(turn.id),
            {
                "id": turn.id,
                "session_id": turn.session_id,
                "role": turn.role,
                "content": turn.content,
                "timestamp": turn.timestamp.isoformat(),
                "run_id": turn.run_id or "",
                "tool_calls": json.dumps([tc.model_dump(mode="json") for tc in turn.tool_calls]),
                "tool_call_id": turn.tool_call_id or "",
                "tokens_in": str(turn.tokens_in),
                "tokens_out": str(turn.tokens_out),
                "cost_usd": str(turn.cost_usd),
                "metadata": json.dumps(dict(turn.metadata)),
            },
        )
        await self._r.zadd(_TURNS_INDEX_KEY.format(turn.session_id), {turn.id: ts})
        await self._upsert_session(turn.session_id, turn.timestamp)
        await self._maybe_expire(turn.session_id)

    async def _upsert_session(self, session_id: str, ts: datetime) -> None:
        existing = await self._r.hgetall(_SESSION_KEY.format(session_id))
        if not existing:
            await self._r.hset(
                _SESSION_KEY.format(session_id),
                {
                    "id": session_id,
                    "owner": "",
                    "created_at": ts.isoformat(),
                    "last_active_at": ts.isoformat(),
                    "metadata": "{}",
                },
            )
            await self._r.sadd(_SESSIONS_INDEX_KEY, session_id)
        else:
            await self._r.hset(
                _SESSION_KEY.format(session_id),
                {"last_active_at": ts.isoformat()},
            )

    async def _maybe_expire(self, session_id: str) -> None:
        if self._ttl_seconds is None:
            return
        await self._r.expire(_TURNS_INDEX_KEY.format(session_id), self._ttl_seconds)
        await self._r.expire(_SESSION_KEY.format(session_id), self._ttl_seconds)

    async def load(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        roles: list[str] | None = None,
    ) -> list[ChatTurn]:
        min_score = after.timestamp() if after is not None else float("-inf")
        max_score = before.timestamp() if before is not None else float("inf")
        ids = await self._r.zrangebyscore(_TURNS_INDEX_KEY.format(session_id), min_score, max_score)
        turns: list[ChatTurn] = []
        for turn_id in ids:
            raw = await self._r.hgetall(_TURN_KEY.format(turn_id))
            if not raw:
                continue
            turn = _hash_to_turn(raw)
            if roles is not None and turn.role not in roles:
                continue
            turns.append(turn)
        turns.sort(key=lambda t: t.timestamp)
        if limit is not None:
            turns = turns[:limit]
        return turns

    async def count(self, session_id: str) -> int:
        ids = await self._r.zrange(_TURNS_INDEX_KEY.format(session_id), 0, -1)
        return len(ids)

    async def delete_session(self, session_id: str) -> int:
        ids = await self._r.zrange(_TURNS_INDEX_KEY.format(session_id), 0, -1)
        removed = 0
        for turn_id in ids:
            removed += await self._r.delete(_TURN_KEY.format(turn_id))
        await self._r.delete(_TURNS_INDEX_KEY.format(session_id))
        await self._r.delete(_SESSION_KEY.format(session_id))
        await self._r.srem(_SESSIONS_INDEX_KEY, session_id)
        return removed

    async def list_sessions(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[SessionInfo]:
        all_ids = await self._r.smembers(_SESSIONS_INDEX_KEY)
        sessions: list[SessionInfo] = []
        for sid in all_ids:
            info = await self._load_session_info(sid)
            if info is None:
                continue
            if owner is not None and info.owner != owner:
                continue
            if before is not None and info.last_active_at >= before:
                continue
            sessions.append(info)
        sessions.sort(key=lambda s: s.last_active_at, reverse=True)
        return sessions[:limit]

    async def update_session_metadata(self, session_id: str, metadata: Mapping[str, Any]) -> None:
        raw = await self._r.hgetall(_SESSION_KEY.format(session_id))
        if not raw:
            # Create the session if it doesn't exist yet (bug-018):
            # ChatServer records owner/metadata before the first turn.
            now = datetime.now(UTC).isoformat()
            await self._r.hset(
                _SESSION_KEY.format(session_id),
                {
                    "id": session_id,
                    "owner": "",
                    "created_at": now,
                    "last_active_at": now,
                    "metadata": "{}",
                },
            )
            await self._r.sadd(_SESSIONS_INDEX_KEY, session_id)
            raw = {"metadata": "{}"}
        existing: dict[str, Any] = json.loads(raw.get("metadata", "{}"))
        existing.update(dict(metadata))
        update: dict[str, str] = {"metadata": json.dumps(existing)}
        if "owner" in metadata:
            update["owner"] = str(metadata["owner"] or "")
        await self._r.hset(_SESSION_KEY.format(session_id), update)

    async def expire_before(self, cutoff: datetime) -> int:
        all_ids = await self._r.smembers(_SESSIONS_INDEX_KEY)
        removed = 0
        for sid in all_ids:
            info = await self._load_session_info(sid)
            if info is None or info.last_active_at >= cutoff:
                continue
            await self.delete_session(sid)
            removed += 1
        return removed

    def capabilities(self) -> set[str]:
        return {"ttl", "streaming_load"}

    async def _load_session_info(self, session_id: str) -> SessionInfo | None:
        raw = await self._r.hgetall(_SESSION_KEY.format(session_id))
        if not raw:
            return None
        ids = await self._r.zrange(_TURNS_INDEX_KEY.format(session_id), 0, -1)
        total = 0.0
        for turn_id in ids:
            turn_raw = await self._r.hgetall(_TURN_KEY.format(turn_id))
            if not turn_raw:
                continue
            total += float(turn_raw.get("cost_usd", "0") or 0.0)
        owner = raw.get("owner", "") or None
        return SessionInfo(
            id=raw["id"],
            owner=owner,
            created_at=datetime.fromisoformat(raw["created_at"]),
            last_active_at=datetime.fromisoformat(raw["last_active_at"]),
            turn_count=len(ids),
            total_cost_usd=total,
            metadata=json.loads(raw.get("metadata", "{}")),
        )


async def _build_client_runner(url: str) -> RedisRunner:  # pragma: no cover — live only
    try:
        import redis.asyncio as redis_asyncio  # noqa: PLC0415
    except ImportError as exc:
        msg = "redis is not installed. Install via `pip install redis` to use RedisChatHistory."
        raise ModuleError(msg) from exc
    from agentforge_chat_history_redis._runner import _RedisClientRunner  # noqa: PLC0415

    client = redis_asyncio.Redis.from_url(url)
    return _RedisClientRunner(client)


def _hash_to_turn(raw: dict[str, str]) -> ChatTurn:
    tool_calls_raw = json.loads(raw.get("tool_calls", "[]"))
    raw_role = raw["role"]
    if raw_role not in _ALLOWED_ROLES:  # pragma: no cover — defensive
        msg = f"Invalid ChatTurn role from Redis: {raw_role!r}"
        raise ModuleError(msg)
    role: ChatRole = raw_role
    return ChatTurn(
        id=raw["id"],
        session_id=raw["session_id"],
        role=role,
        content=raw["content"],
        timestamp=_parse_ts(raw["timestamp"]),
        run_id=raw.get("run_id") or None,
        tool_calls=tuple(ToolCall.model_validate(tc) for tc in tool_calls_raw),
        tool_call_id=raw.get("tool_call_id") or None,
        tokens_in=int(raw.get("tokens_in", "0")),
        tokens_out=int(raw.get("tokens_out", "0")),
        cost_usd=float(raw.get("cost_usd", "0")),
        metadata=json.loads(raw.get("metadata", "{}")),
    )


def _parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:  # pragma: no cover — defensive (we always write tz-aware)
        return parsed.replace(tzinfo=UTC)
    return parsed


__all__ = ["RedisChatHistory"]
