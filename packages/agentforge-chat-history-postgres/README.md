# agentforge-chat-history-postgres

Postgres-backed `ChatHistoryStore` for AgentForge (feat-020 v0.2).

Sister package to [`agentforge-memory-postgres`](../agentforge-memory-postgres).
Drop-in replacement for `SqliteChatHistory` when chat sessions
need multi-writer concurrency or managed-database guarantees
(Neon / Supabase / RDS / Cloud SQL).

```python
from agentforge_chat_history_postgres import PostgresChatHistory

history = await PostgresChatHistory.from_dsn(
    "postgresql://user:pw@host:5432/agentforge"
)
```

Implements the locked `ChatHistoryStore` contract from
`agentforge-core` plus `init_schema()` that creates the
`chat_sessions` + `chat_turns` tables idempotently
(`CREATE TABLE IF NOT EXISTS`).

Run live integration tests with:

```bash
RUN_LIVE_POSTGRES_DSN=postgresql://postgres:test@localhost:5432/postgres \
  uv run pytest -m live packages/agentforge-chat-history-postgres/
```
