"""`SqliteChatHistory` — `ChatHistoryStore` over SQLite via aiosqlite.

Two tables: ``chat_turns`` (one row per turn) and ``chat_sessions``
(one row per session). Indexed on ``(session_id, created_at)`` so
``load()`` is sub-linear w.r.t. total turn count.

Schema is created via ``init_schema()`` / ``from_path()``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

import aiosqlite
from agentforge_core.contracts.chat import ChatHistoryStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.chat import ChatTurn, SessionInfo
from agentforge_core.values.messages import ToolCall

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id              TEXT PRIMARY KEY,
    owner           TEXT,
    created_at      TEXT NOT NULL,
    last_active_at  TEXT NOT NULL,
    metadata        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_owner
    ON chat_sessions(owner);
CREATE INDEX IF NOT EXISTS idx_sessions_last_active
    ON chat_sessions(last_active_at);
CREATE TABLE IF NOT EXISTS chat_turns (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    run_id          TEXT,
    tool_calls      TEXT NOT NULL,
    tool_call_id    TEXT,
    tokens_in       INTEGER NOT NULL,
    tokens_out      INTEGER NOT NULL,
    cost_usd        REAL NOT NULL,
    metadata        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_turns_session_ts
    ON chat_turns(session_id, timestamp);
"""


class SqliteChatHistory(ChatHistoryStore):
    """`ChatHistoryStore` backed by a single SQLite file."""

    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self._db = connection

    @classmethod
    async def from_path(cls, path: str | Path) -> SqliteChatHistory:
        """Open or create a SQLite database at ``path``.

        ``":memory:"`` is allowed for tests; on disk the parent
        directory must already exist.
        """
        connection = await aiosqlite.connect(str(path))
        connection.row_factory = aiosqlite.Row
        await connection.executescript(_SCHEMA_SQL)
        await connection.commit()
        return cls(connection=connection)

    async def __aenter__(self) -> SqliteChatHistory:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._db.close()

    async def append(self, turn: ChatTurn) -> None:
        ts_iso = turn.timestamp.isoformat()
        await self._db.execute(
            """INSERT OR REPLACE INTO chat_turns
               (id, session_id, role, content, timestamp, run_id,
                tool_calls, tool_call_id, tokens_in, tokens_out,
                cost_usd, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                turn.id,
                turn.session_id,
                turn.role,
                turn.content,
                ts_iso,
                turn.run_id,
                json.dumps([tc.model_dump(mode="json") for tc in turn.tool_calls]),
                turn.tool_call_id,
                turn.tokens_in,
                turn.tokens_out,
                turn.cost_usd,
                json.dumps(turn.metadata),
            ),
        )
        await self._upsert_session(turn.session_id, ts_iso)
        await self._db.commit()

    async def _upsert_session(self, session_id: str, now_iso: str) -> None:
        await self._db.execute(
            """INSERT INTO chat_sessions
               (id, owner, created_at, last_active_at, metadata)
               VALUES (?, NULL, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET last_active_at=excluded.last_active_at""",
            (session_id, now_iso, now_iso, "{}"),
        )

    async def load(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        roles: list[str] | None = None,
    ) -> list[ChatTurn]:
        where = ["session_id = ?"]
        params: list[Any] = [session_id]
        if before is not None:
            where.append("timestamp < ?")
            params.append(before.isoformat())
        if after is not None:
            where.append("timestamp > ?")
            params.append(after.isoformat())
        if roles is not None:
            placeholders = ", ".join("?" * len(roles))
            where.append(f"role IN ({placeholders})")  # nosec B608 — `?` placeholders only
            params.extend(roles)
        sql = (
            "SELECT * FROM chat_turns WHERE "  # noqa: S608  # nosec B608
            + " AND ".join(where)
            + " ORDER BY timestamp"
        )
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [_row_to_turn(row) for row in rows]

    async def count(self, session_id: str) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) FROM chat_turns WHERE session_id = ?",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def delete_session(self, session_id: str) -> int:
        cur = await self._db.execute(
            "DELETE FROM chat_turns WHERE session_id = ?",
            (session_id,),
        )
        removed = cur.rowcount or 0
        await self._db.execute(
            "DELETE FROM chat_sessions WHERE id = ?",
            (session_id,),
        )
        await self._db.commit()
        return removed

    async def list_sessions(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[SessionInfo]:
        where: list[str] = []
        params: list[Any] = []
        if owner is not None:
            where.append("owner = ?")
            params.append(owner)
        if before is not None:
            where.append("last_active_at < ?")
            params.append(before.isoformat())
        sql = "SELECT * FROM chat_sessions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY last_active_at DESC LIMIT ?"  # nosec B608
        params.append(limit)
        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [await self._row_to_info(row) for row in rows]

    async def update_session_metadata(self, session_id: str, metadata: Mapping[str, Any]) -> None:
        # Create the session row if it doesn't exist yet (bug-018):
        # ChatServer records owner/metadata before the first turn is
        # appended. DO NOTHING leaves an existing row (and its
        # last_active_at) untouched.
        now_iso = datetime.now(UTC).isoformat()
        await self._db.execute(
            """INSERT INTO chat_sessions
               (id, owner, created_at, last_active_at, metadata)
               VALUES (?, NULL, ?, ?, ?)
               ON CONFLICT(id) DO NOTHING""",
            (session_id, now_iso, now_iso, "{}"),
        )
        async with self._db.execute(
            "SELECT metadata, owner FROM chat_sessions WHERE id = ?",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:  # pragma: no cover — the INSERT above guarantees a row
            raise ModuleError(f"Cannot update metadata for unknown session {session_id!r}")
        existing = json.loads(row["metadata"])
        existing.update(dict(metadata))
        owner = metadata.get("owner", row["owner"])
        await self._db.execute(
            "UPDATE chat_sessions SET metadata = ?, owner = ? WHERE id = ?",
            (json.dumps(existing), owner, session_id),
        )
        await self._db.commit()

    async def expire_before(self, cutoff: datetime) -> int:
        cutoff_iso = cutoff.isoformat()
        await self._db.execute(
            """DELETE FROM chat_turns WHERE session_id IN (
                 SELECT id FROM chat_sessions WHERE last_active_at < ?
               )""",
            (cutoff_iso,),
        )
        cur = await self._db.execute(
            "DELETE FROM chat_sessions WHERE last_active_at < ?",
            (cutoff_iso,),
        )
        removed = cur.rowcount or 0
        await self._db.commit()
        return removed

    def capabilities(self) -> set[str]:
        return {"ttl"}

    async def _row_to_info(self, row: Any) -> SessionInfo:
        async with self._db.execute(
            "SELECT COUNT(*), COALESCE(SUM(cost_usd), 0.0) FROM chat_turns WHERE session_id = ?",
            (row["id"],),
        ) as cur:
            agg = await cur.fetchone()
        count = int(agg[0]) if agg else 0
        cost = float(agg[1]) if agg else 0.0
        return SessionInfo(
            id=row["id"],
            owner=row["owner"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_active_at=datetime.fromisoformat(row["last_active_at"]),
            turn_count=count,
            total_cost_usd=cost,
            metadata=json.loads(row["metadata"]),
        )


def _row_to_turn(row: Any) -> ChatTurn:
    raw_calls = json.loads(row["tool_calls"])
    tool_calls = tuple(ToolCall.model_validate(tc) for tc in raw_calls)
    return ChatTurn(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        run_id=row["run_id"],
        tool_calls=tool_calls,
        tool_call_id=row["tool_call_id"],
        tokens_in=int(row["tokens_in"]),
        tokens_out=int(row["tokens_out"]),
        cost_usd=float(row["cost_usd"]),
        metadata=json.loads(row["metadata"]),
    )


__all__ = ["SqliteChatHistory"]
