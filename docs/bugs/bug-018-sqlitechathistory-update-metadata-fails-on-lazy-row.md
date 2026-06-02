---
status: open
severity: P0
found-in: v0.2.3
found-via: live integration of a Bedrock-backed MCP agent (Khemchand Joshi, 2026-05-27)
---

# bug-018 — `SqliteChatHistory.update_session_metadata` raises on the row `_create_session` will create

## Symptom

Every `POST /chat/sessions` (the documented session-creation route on
`ChatServer`) returns **500 Internal Server Error** with:

```
agentforge_core.production.exceptions.ModuleError:
  Cannot update metadata for unknown session '<session_id>'
```

So no chat session can be created on a fresh process when using the
shipped SQLite chat-history driver.

## Reproduction

```python
from agentforge_chat import SqliteChatHistory
from agentforge_chat_http import ChatServer

history = await SqliteChatHistory.from_path("c.db")
server = ChatServer(agent_factory=..., history_store=history, auth=...)
# In any HTTP client: POST /chat/sessions {} → 500
```

Or directly:

```python
await history.update_session_metadata("brand-new-id", {"owner": "x"})
# → ModuleError: Cannot update metadata for unknown session 'brand-new-id'
```

## Root cause

Two interacting points:

1. `SqliteChatHistory._upsert_session` is lazy — it only inserts the
   `chat_sessions` row on the **first `append(turn)`**, not at
   construction time. Until a turn is appended, the row doesn't exist.
2. `ChatServer._create_session` (agentforge_chat_http/server.py:286)
   constructs the `ChatSession` object and immediately calls
   `history.update_session_metadata(session.session_id, {"owner": ...})`
   — **before** any turn is appended. The row doesn't exist yet, so
   `update_session_metadata` (line 209) raises.

So the framework's own `ChatServer` flow violates the `SqliteChatHistory`
contract. Symmetric bug: either the chat-history needs an explicit
`create_session` step, or `update_session_metadata` should upsert.

## Fix proposal

Pick one:

1. **`update_session_metadata` upserts the row** if missing. Trivial
   change in `SqliteChatHistory.update_session_metadata`:

   ```python
   await self._db.execute(
       """INSERT INTO chat_sessions (id, owner, created_at, last_active_at, metadata)
          VALUES (?, NULL, ?, ?, ?)
          ON CONFLICT(id) DO NOTHING""",
       (session_id, now_iso, now_iso, "{}"),
   )
   # then existing UPDATE
   ```

2. **Add `ChatHistoryStore.create_session()`** to the ABC and call it
   from `ChatServer._create_session` before `update_session_metadata`.
   Cleaner contract but requires updating every driver
   (sqlite, postgres, redis, in-memory).

Option 1 is the minimum patch. Option 2 is the right long-term shape.

## Workaround

Downstream consumers can subclass `SqliteChatHistory` and override
`update_session_metadata` to upsert first. downstream consumers ship
`CustomChatHistory` in `a custom ChatHistory subclass`
with this exact pattern.

## Framework-level vs derived-agent-level

**Framework.** Both halves of the contract violation are
framework-shipped: the caller (`ChatServer._create_session`,
`agentforge-chat-http`) and the store (`SqliteChatHistory`,
`agentforge-chat`). The `ChatHistoryStore` ABC docstring promises
"merge metadata into the session's metadata dict" with no precondition
that the session already exist — so the framework's own server violates
its own store's contract on the very first request.

- **Derived-agent test:** the consumer's only workaround is to subclass
  the framework's store and override a method to patch over a framework
  contract bug. That's monkey-patching framework behaviour → framework
  defect, full stop.
- **How the fix helps derived agents:** `POST /chat/sessions` works out
  of the box with the shipped SQLite driver. Option 2 (add
  `create_session()` to the ABC) additionally makes the create/update
  contract explicit for *every* driver (sqlite/postgres/redis/in-memory),
  so third-party drivers can't reintroduce the same gap.

## Verification note (2026-06-02)

All three sub-claims **confirmed** against source: `_upsert_session` is
lazy (only called from `append()`, `sqlite.py:112`);
`update_session_metadata` does SELECT-then-raise with no INSERT
(`sqlite.py:202-209`); `_create_session` calls it before any append
(`agentforge_chat_http/server.py:286`). Reproduced empirically — fresh
store raises `ModuleError` on first `update_session_metadata`. The
recommended landing is **option 1 now** (upsert; minimal, unblocks) plus
**option 2 as the contract fix** in the same PR.
