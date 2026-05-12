# agentforge-chat-slack

Reference Slack channel adapter for AgentForge (feat-020 v0.2).

Maps `message` + `app_mention` events to `ChatSession.send`,
posts a placeholder message, and batches `chat.update` calls as
text chunks stream back from the agent. Slack rate-limits per
channel, so true per-token updates aren't practical — the
adapter batches every `batch_window_s` seconds (default 0.5 s).

Exemplar of how to wire any messaging channel to AgentForge
(Telegram / Discord / Teams would follow the same shape with
their SDKs).

```python
from agentforge_chat_slack import SlackChatAdapter

adapter = SlackChatAdapter(
    bot_token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    session_factory=lambda channel_id: ChatSession(
        agent=build_agent(),
        session_id=channel_id,
    ),
)
await adapter.start()
```

Live integration test gated on `SLACK_BOT_TOKEN` +
`SLACK_TEST_CHANNEL` env vars. Developer-machine only — no
free CI Slack workspace.
