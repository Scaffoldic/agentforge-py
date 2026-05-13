"""`PostgresChatHistory` — `ChatHistoryStore` over Postgres via asyncpg.

Two tables (mirrors `SqliteChatHistory`): `chat_sessions`
(one row per session) and `chat_turns` (one row per turn, with
composite index on `(session_id, timestamp)` so `load()` stays
sub-linear w.r.t. total turn count).

Schema is created via `init_schema()` / `from_dsn()` using
`CREATE TABLE IF NOT EXISTS` — no migration framework in v0.2.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from agentforge_core.contracts.chat import ChatHistoryStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.chat import ChatTurn, SessionInfo
from agentforge_core.values.messages import ToolCall

from agentforge_chat_history_postgres._runner import PostgresRunner

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id              TEXT PRIMARY KEY,
    owner           TEXT,
    created_at      TIMESTAMPTZ NOT NULL,
    last_active_at  TIMESTAMPTZ NOT NULL,
    metadata        JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_owner
    ON chat_sessions(owner);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_active
    ON chat_sessions(last_active_at);
CREATE TABLE IF NOT EXISTS chat_turns (
    id              TEXT PRIMARY KEY,
    session_id      TEXT        NOT NULL,
    role            TEXT        NOT NULL,
    content         TEXT        NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    run_id          TEXT,
    tool_calls      JSONB       NOT NULL,
    tool_call_id    TEXT,
    tokens_in       INTEGER     NOT NULL,
    tokens_out      INTEGER     NOT NULL,
    cost_usd        DOUBLE PRECISION NOT NULL,
    metadata        JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_turns_session_ts
    ON chat_turns(session_id, timestamp);
"""


class PostgresChatHistory(ChatHistoryStore):
    """`ChatHistoryStore` backed by a Postgres database."""

    def __init__(self, *, runner: PostgresRunner) -> None:
        self._r = runner

    @classmethod
    async def from_dsn(
        cls,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        runner: PostgresRunner | None = None,
    ) -> PostgresChatHistory:
        """Open a connection pool against ``dsn`` and bootstrap the schema."""
        if runner is None:  # pragma: no cover — production path; exercised via `-m live`
            runner = await _build_pool_runner(dsn, min_size=min_size, max_size=max_size)
        store = cls(runner=runner)
        await store.init_schema()
        return store

    async def init_schema(self) -> None:
        for stmt in _split_statements(_SCHEMA_SQL):
            await self._r.execute(stmt)

    async def close(self) -> None:
        await self._r.close()

    async def append(self, turn: ChatTurn) -> None:
        await self._r.execute(
            """INSERT INTO chat_turns
               (id, session_id, role, content, timestamp, run_id,
                tool_calls, tool_call_id, tokens_in, tokens_out,
                cost_usd, metadata)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
               ON CONFLICT (id) DO UPDATE SET
                 content = EXCLUDED.content,
                 timestamp = EXCLUDED.timestamp,
                 run_id = EXCLUDED.run_id,
                 tool_calls = EXCLUDED.tool_calls,
                 tool_call_id = EXCLUDED.tool_call_id,
                 tokens_in = EXCLUDED.tokens_in,
                 tokens_out = EXCLUDED.tokens_out,
                 cost_usd = EXCLUDED.cost_usd,
                 metadata = EXCLUDED.metadata""",
            turn.id,
            turn.session_id,
            turn.role,
            turn.content,
            turn.timestamp,
            turn.run_id,
            json.dumps([tc.model_dump(mode="json") for tc in turn.tool_calls]),
            turn.tool_call_id,
            turn.tokens_in,
            turn.tokens_out,
            turn.cost_usd,
            json.dumps(dict(turn.metadata)),
        )
        await self._upsert_session(turn.session_id, turn.timestamp)

    async def _upsert_session(self, session_id: str, ts: datetime) -> None:
        await self._r.execute(
            """INSERT INTO chat_sessions
                 (id, owner, created_at, last_active_at, metadata)
               VALUES ($1, NULL, $2, $2, '{}'::jsonb)
               ON CONFLICT (id) DO UPDATE
                 SET last_active_at = EXCLUDED.last_active_at""",
            session_id,
            ts,
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
        clauses = ["session_id = $1"]
        params: list[Any] = [session_id]
        if before is not None:
            clauses.append(f"timestamp < ${len(params) + 1}")
            params.append(before)
        if after is not None:
            clauses.append(f"timestamp > ${len(params) + 1}")
            params.append(after)
        if roles is not None:
            clauses.append(f"role = ANY(${len(params) + 1}::text[])")
            params.append(list(roles))
        sql = (
            "SELECT * FROM chat_turns WHERE "  # noqa: S608  # nosec B608 — placeholders only
            + " AND ".join(clauses)
            + " ORDER BY timestamp"
        )
        if limit is not None:
            sql += f" LIMIT ${len(params) + 1}"
            params.append(limit)
        rows = await self._r.fetch(sql, *params)
        return [_row_to_turn(row) for row in rows]

    async def count(self, session_id: str) -> int:
        row = await self._r.fetchrow(
            "SELECT COUNT(*) AS n FROM chat_turns WHERE session_id = $1",
            session_id,
        )
        return int(row["n"]) if row is not None else 0

    async def delete_session(self, session_id: str) -> int:
        removed = await self._r.execute_returning_count(
            "DELETE FROM chat_turns WHERE session_id = $1",
            session_id,
        )
        await self._r.execute(
            "DELETE FROM chat_sessions WHERE id = $1",
            session_id,
        )
        return removed

    async def list_sessions(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[SessionInfo]:
        clauses: list[str] = []
        params: list[Any] = []
        if owner is not None:
            clauses.append(f"owner = ${len(params) + 1}")
            params.append(owner)
        if before is not None:
            clauses.append(f"last_active_at < ${len(params) + 1}")
            params.append(before)
        sql = "SELECT * FROM chat_sessions"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += f" ORDER BY last_active_at DESC LIMIT ${len(params) + 1}"  # nosec B608
        params.append(limit)
        rows = await self._r.fetch(sql, *params)
        return [await self._row_to_info(row) for row in rows]

    async def update_session_metadata(self, session_id: str, metadata: Mapping[str, Any]) -> None:
        row = await self._r.fetchrow(
            "SELECT owner, metadata FROM chat_sessions WHERE id = $1",
            session_id,
        )
        if row is None:
            raise ModuleError(f"Cannot update metadata for unknown session {session_id!r}")
        existing: dict[str, Any] = dict(_coerce_jsonb(row["metadata"]))
        existing.update(dict(metadata))
        owner = metadata.get("owner", row["owner"])
        await self._r.execute(
            "UPDATE chat_sessions SET metadata = $1::jsonb, owner = $2 WHERE id = $3",
            json.dumps(existing),
            owner,
            session_id,
        )

    async def expire_before(self, cutoff: datetime) -> int:
        await self._r.execute(
            """DELETE FROM chat_turns
               WHERE session_id IN (
                 SELECT id FROM chat_sessions WHERE last_active_at < $1
               )""",
            cutoff,
        )
        return await self._r.execute_returning_count(
            "DELETE FROM chat_sessions WHERE last_active_at < $1",
            cutoff,
        )

    def capabilities(self) -> set[str]:
        return {"ttl", "encryption_at_rest", "full_text_search"}

    async def _row_to_info(self, row: Any) -> SessionInfo:
        agg = await self._r.fetchrow(
            """SELECT COUNT(*) AS n,
                      COALESCE(SUM(cost_usd), 0.0) AS total
               FROM chat_turns WHERE session_id = $1""",
            row["id"],
        )
        count = int(agg["n"]) if agg is not None else 0
        total = float(agg["total"]) if agg is not None else 0.0
        return SessionInfo(
            id=row["id"],
            owner=row["owner"],
            created_at=row["created_at"],
            last_active_at=row["last_active_at"],
            turn_count=count,
            total_cost_usd=total,
            metadata=dict(_coerce_jsonb(row["metadata"])),
        )


async def _build_pool_runner(  # pragma: no cover — exercised only with `-m live`
    dsn: str,
    *,
    min_size: int,
    max_size: int,
) -> PostgresRunner:
    try:
        import asyncpg  # noqa: PLC0415
    except ImportError as exc:
        msg = (
            "asyncpg is not installed. Install via `pip install asyncpg` "
            "to use PostgresChatHistory."
        )
        raise ModuleError(msg) from exc
    from agentforge_chat_history_postgres._runner import _AsyncpgPoolRunner  # noqa: PLC0415

    pool = await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)
    return _AsyncpgPoolRunner(pool)


def _coerce_jsonb(value: Any) -> dict[str, Any]:
    if value is None:  # pragma: no cover — defensive for asyncpg JSON variants
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):  # pragma: no cover — asyncpg returns str when JSONB codec absent
        parsed: Any = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}  # pragma: no cover — defensive fallback


def _row_to_turn(row: Any) -> ChatTurn:
    raw_calls = _coerce_jsonb_list(row["tool_calls"])
    tool_calls = tuple(ToolCall.model_validate(tc) for tc in raw_calls)
    return ChatTurn(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        timestamp=row["timestamp"],
        run_id=row["run_id"],
        tool_calls=tool_calls,
        tool_call_id=row["tool_call_id"],
        tokens_in=int(row["tokens_in"]),
        tokens_out=int(row["tokens_out"]),
        cost_usd=float(row["cost_usd"]),
        metadata=dict(_coerce_jsonb(row["metadata"])),
    )


def _coerce_jsonb_list(value: Any) -> list[Any]:
    if value is None:  # pragma: no cover — defensive for asyncpg JSON variants
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):  # pragma: no cover — asyncpg returns str when JSONB codec absent
        parsed: Any = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    return []  # pragma: no cover — defensive fallback


def _split_statements(sql: str) -> list[str]:
    return [s.strip() for s in sql.split(";") if s.strip()]


__all__ = ["PostgresChatHistory"]
