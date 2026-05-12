# agentforge-chat-http

FastAPI server for `agentforge-chat`: REST + WebSocket + SSE,
bearer auth, in-process rate limiting, multi-tenant session
isolation.

See [`docs/features/feat-020-chat-agents.md`](https://github.com/Scaffoldic/agentforge-py/blob/main/docs/features/feat-020-chat-agents.md)
§4.1 for the HTTP wire format.

## Install

```bash
pip install agentforge-chat-http
```

## Run a chat server

```python
import asyncio
from agentforge import Agent
from agentforge_chat import InMemoryChatHistory
from agentforge_chat_http import ChatServer, EnvBearerAuth

async def main() -> None:
    server = ChatServer(
        agent_factory=lambda: Agent(model="anthropic:claude-sonnet-4-6", strategy="react"),
        history_store=InMemoryChatHistory(),
        auth=EnvBearerAuth("API_TOKENS"),
        host="0.0.0.0",
        port=8080,
    )
    await server.serve()

asyncio.run(main())
```
