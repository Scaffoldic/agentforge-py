# agentforge-chat-history-redis

Redis-backed `ChatHistoryStore` for AgentForge (feat-020 v0.2).

Also ships `RedisSessionLock` — the cross-process per-session
lock used by multi-worker chat-http deployments so a single
session can't be processed concurrently across pods.

```python
from agentforge_chat_history_redis import (
    RedisChatHistory,
    redis_session_lock_factory,
)

history = await RedisChatHistory.from_url("redis://localhost:6379")
lock_factory = redis_session_lock_factory("redis://localhost:6379")
```

Run live integration tests with:

```bash
docker run --rm -d -p 6379:6379 redis:7
REDIS_URL=redis://localhost:6379 \
  uv run pytest -m live packages/agentforge-chat-history-redis/
```
