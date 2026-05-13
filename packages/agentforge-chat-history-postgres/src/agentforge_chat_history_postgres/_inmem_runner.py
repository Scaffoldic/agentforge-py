"""In-memory `PostgresFakeRunner` for unit tests (feat-020 v0.2).

Interprets the narrow SQL vocabulary `PostgresChatHistory` emits and
routes operations to in-memory backings. Mirrors the pattern used by
`agentforge-memory-postgres`. Lets the conformance suite run without
a real Postgres instance — live tests in `tests/integration/` cover
the real driver.

The fake handles enough SQL to exercise every code path in
`history.py`:

- `INSERT INTO chat_turns ... ON CONFLICT` / `INSERT INTO chat_sessions`
- `SELECT * FROM chat_turns WHERE session_id = $1 [AND ...] ORDER BY timestamp [LIMIT $N]`
- `SELECT COUNT(*) AS n FROM chat_turns WHERE session_id = $1`
- `SELECT * FROM chat_sessions [WHERE ...] ORDER BY last_active_at DESC LIMIT $N`
- `SELECT owner, metadata FROM chat_sessions WHERE id = $1`
- `SELECT COUNT(*), COALESCE(SUM(cost_usd), 0.0) FROM chat_turns WHERE session_id = $1`
- `UPDATE chat_sessions SET metadata = $1::jsonb, owner = $2 WHERE id = $3`
- `DELETE FROM chat_turns WHERE session_id = $1`
- `DELETE FROM chat_sessions WHERE id = $1`
- `DELETE FROM chat_turns WHERE session_id IN (... last_active_at < $1)`
- `DELETE FROM chat_sessions WHERE last_active_at < $1`
- `CREATE TABLE IF NOT EXISTS ...` / `CREATE INDEX IF NOT EXISTS ...` (no-op).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class _FakeRecord(dict[str, Any]):
    """Dict that supports asyncpg-style `record["col"]` access."""


class PostgresFakeRunner:
    """In-memory emulation of the SQL the driver emits."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._turns: dict[str, dict[str, Any]] = {}
        self.closed = False

    async def fetch(self, sql: str, *params: Any) -> list[Any]:
        sql_n = _norm(sql)
        if sql_n.startswith("select * from chat_turns where session_id = $1"):
            return self._select_turns(sql_n, params)
        if sql_n.startswith("select * from chat_sessions"):
            return self._select_sessions(sql_n, params)
        msg = f"PostgresFakeRunner: unsupported fetch sql: {sql_n!r}"
        raise NotImplementedError(msg)

    async def fetchrow(self, sql: str, *params: Any) -> Any | None:
        sql_n = _norm(sql)
        if sql_n.startswith("select count(*) as n from chat_turns where session_id = $1"):
            session_id = params[0]
            count = sum(1 for t in self._turns.values() if t["session_id"] == session_id)
            return _FakeRecord(n=count)
        if sql_n.startswith("select owner, metadata from chat_sessions where id = $1"):
            session = self._sessions.get(params[0])
            if session is None:
                return None
            return _FakeRecord(owner=session["owner"], metadata=dict(session["metadata"]))
        if sql_n.startswith("select count(*) as n, coalesce(sum(cost_usd), 0.0) as total"):
            session_id = params[0]
            matched = [t for t in self._turns.values() if t["session_id"] == session_id]
            return _FakeRecord(
                n=len(matched),
                total=sum(float(t["cost_usd"]) for t in matched),
            )
        msg = f"PostgresFakeRunner: unsupported fetchrow sql: {sql_n!r}"
        raise NotImplementedError(msg)

    async def execute(self, sql: str, *params: Any) -> None:
        sql_n = _norm(sql)
        if sql_n.startswith("create"):
            return
        if sql_n.startswith("insert into chat_turns"):
            self._insert_turn(params)
            return
        if sql_n.startswith("insert into chat_sessions"):
            self._upsert_session(params[0], params[1])
            return
        if sql_n.startswith("update chat_sessions set metadata"):
            metadata_json, owner, session_id = params
            import json  # noqa: PLC0415

            self._sessions[session_id]["metadata"] = json.loads(metadata_json)
            self._sessions[session_id]["owner"] = owner
            return
        if sql_n.startswith("delete from chat_turns where session_id in"):
            cutoff = params[0]
            kill = {sid for sid, s in self._sessions.items() if s["last_active_at"] < cutoff}
            self._turns = {tid: t for tid, t in self._turns.items() if t["session_id"] not in kill}
            return
        if sql_n.startswith("delete from chat_sessions where id = $1"):
            session_id = params[0]
            self._sessions.pop(session_id, None)
            return
        msg = f"PostgresFakeRunner: unsupported execute sql: {sql_n!r}"
        raise NotImplementedError(msg)

    async def execute_returning_count(self, sql: str, *params: Any) -> int:
        sql_n = _norm(sql)
        if sql_n.startswith("delete from chat_turns where session_id = $1"):
            session_id = params[0]
            before = len(self._turns)
            self._turns = {
                tid: t for tid, t in self._turns.items() if t["session_id"] != session_id
            }
            return before - len(self._turns)
        if sql_n.startswith("delete from chat_sessions where last_active_at < $1"):
            cutoff = params[0]
            before = len(self._sessions)
            self._sessions = {
                sid: s for sid, s in self._sessions.items() if s["last_active_at"] >= cutoff
            }
            return before - len(self._sessions)
        msg = f"PostgresFakeRunner: unsupported execute_returning_count sql: {sql_n!r}"
        raise NotImplementedError(msg)

    async def close(self) -> None:
        self.closed = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _insert_turn(self, params: tuple[Any, ...]) -> None:
        import json  # noqa: PLC0415

        (
            turn_id,
            session_id,
            role,
            content,
            timestamp,
            run_id,
            tool_calls,
            tool_call_id,
            tokens_in,
            tokens_out,
            cost_usd,
            metadata,
        ) = params
        self._turns[turn_id] = {
            "id": turn_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "run_id": run_id,
            "tool_calls": json.loads(tool_calls),
            "tool_call_id": tool_call_id,
            "tokens_in": int(tokens_in),
            "tokens_out": int(tokens_out),
            "cost_usd": float(cost_usd),
            "metadata": json.loads(metadata),
        }

    def _upsert_session(self, session_id: str, ts: datetime) -> None:
        existing = self._sessions.get(session_id)
        if existing is None:
            self._sessions[session_id] = {
                "id": session_id,
                "owner": None,
                "created_at": ts,
                "last_active_at": ts,
                "metadata": {},
            }
        else:
            existing["last_active_at"] = ts

    def _select_turns(self, sql_n: str, params: tuple[Any, ...]) -> list[Any]:
        session_id = params[0]
        matched = [t for t in self._turns.values() if t["session_id"] == session_id]
        # Apply optional filters by inspecting param count + sql snippets.
        idx = 1
        if "timestamp < $" in sql_n:
            before = params[idx]
            matched = [t for t in matched if t["timestamp"] < before]
            idx += 1
        if "timestamp > $" in sql_n:
            after = params[idx]
            matched = [t for t in matched if t["timestamp"] > after]
            idx += 1
        if "role = any(" in sql_n:
            roles = params[idx]
            matched = [t for t in matched if t["role"] in roles]
            idx += 1
        matched.sort(key=lambda t: t["timestamp"])
        if "limit $" in sql_n:
            limit = int(params[idx])
            matched = matched[:limit]
        return [_FakeRecord(t) for t in matched]

    def _select_sessions(self, sql_n: str, params: tuple[Any, ...]) -> list[Any]:
        matched = list(self._sessions.values())
        idx = 0
        if "where owner = $" in sql_n:
            owner = params[idx]
            matched = [s for s in matched if s["owner"] == owner]
            idx += 1
        if "last_active_at < $" in sql_n:
            before = params[idx]
            matched = [s for s in matched if s["last_active_at"] < before]
            idx += 1
        matched.sort(key=lambda s: s["last_active_at"], reverse=True)
        limit = int(params[idx])
        return [_FakeRecord(s) for s in matched[:limit]]


def _norm(sql: str) -> str:
    """Normalise whitespace + lowercase for prefix matching."""
    return " ".join(sql.lower().split()).strip()
