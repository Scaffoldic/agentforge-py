# agentforge-chat

Chat-agent runtime for AgentForge: `ChatSession`,
`InMemoryChatHistory` / `SqliteChatHistory` drivers, and four
truncation strategies (sliding-window, token-budget,
summarise-oldest, hybrid).

See [`docs/features/feat-020-chat-agents.md`](https://github.com/Scaffoldic/agentforge-py/blob/main/docs/features/feat-020-chat-agents.md)
for the design and runbook.

## Install

```bash
pip install agentforge-chat
# or, with the SQLite driver pre-pulled:
pip install "agentforge-chat[sqlite]"
```

## Three-line chat from a one-shot agent

```python
from agentforge import Agent
from agentforge_chat import ChatSession, SqliteChatHistory

agent = Agent(model="anthropic:claude-sonnet-4-6", strategy="react")
session = ChatSession(
    agent=agent,
    history_store=await SqliteChatHistory.from_path("./chat.db"),
)
print((await session.send("Hi")).content)
print((await session.send("What did I just say?")).content)
```
