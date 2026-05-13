"""`SlackChatAdapter` — reference channel adapter (feat-020 v0.2).

Subscribes to Slack `message` and `app_mention` events, maps each
to a `ChatSession.send` call (one session per channel ID), posts a
placeholder message, and batches `chat.update` calls every
`batch_window_s` seconds as text chunks stream back from the
agent. Slack rate-limits per channel, so true per-token streaming
is impractical.

The adapter is concrete-only — no new ABC; the spec calls this out
as a reference impl. Other channel adapters (Telegram / Discord)
follow the same shape with their own SDKs.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from agentforge_chat import ChatSession

from agentforge_chat_slack._runner import SlackRunner

SessionFactory = Callable[[str], ChatSession]
"""Build a `ChatSession` for a given Slack channel ID. The factory
controls session scoping (one per channel, per workspace, per
thread, etc.) — the adapter just calls it once per fresh channel.
"""


class SlackChatAdapter:
    """Maps Slack message events to ChatSession.send + streams replies back.

    Construction:

        SlackChatAdapter(
            session_factory=lambda channel_id: ChatSession(...),
            runner=<production SlackRunner>,
            batch_window_s=0.5,
        )

    Use ``handle_event(channel, text)`` for unit tests; production
    code wires the underlying Slack Bolt app at ``start()`` so
    incoming HTTP events route to ``handle_event``.
    """

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        runner: SlackRunner,
        batch_window_s: float = 0.5,
        placeholder_text: str = "_thinking..._",
    ) -> None:
        self._session_factory = session_factory
        self._runner = runner
        self._batch_window_s = batch_window_s
        self._placeholder_text = placeholder_text
        self._sessions: dict[str, ChatSession] = {}

    async def handle_event(self, channel: str, text: str) -> None:
        """Process one inbound Slack message.

        Posts a placeholder, streams the agent response, and
        batches `chat.update` calls every ``batch_window_s``
        seconds with the cumulative text.
        """
        session = self._sessions.get(channel)
        if session is None:
            session = self._session_factory(channel)
            self._sessions[channel] = session
        ts = await self._runner.post_message(channel, self._placeholder_text)
        cumulative = ""
        last_flush = asyncio.get_event_loop().time()
        pending = ""
        stream = await session.stream(text)
        async for chunk in stream:
            if chunk.kind == "text" and isinstance(chunk.content, str):
                cumulative += chunk.content
                pending = cumulative
                now = asyncio.get_event_loop().time()
                if now - last_flush >= self._batch_window_s:
                    await self._runner.update_message(channel, ts, pending)
                    last_flush = now
            elif chunk.kind == "done":
                break
            elif chunk.kind == "error":
                error_text = self._format_error(chunk.content)
                await self._runner.update_message(channel, ts, error_text)
                return
        # Final flush so the last batch always lands.
        final_text = cumulative if cumulative else self._placeholder_text
        await self._runner.update_message(channel, ts, final_text)

    @staticmethod
    def _format_error(payload: object) -> str:
        if isinstance(payload, dict):
            message = payload.get("message", "")
            return f"⚠️ {message}" if message else "⚠️ chat error"
        return "⚠️ chat error"

    async def start(self) -> None:  # pragma: no cover — exercised via live
        """Mount the Bolt app and serve Slack webhooks.

        Production-only path; needs a configured Bolt app + a host
        process. Unit tests skip this and drive the adapter via
        :meth:`handle_event` directly.
        """
        from slack_bolt.adapter.fastapi.async_handler import (  # noqa: PLC0415
            AsyncSlackRequestHandler,
        )
        from slack_bolt.async_app import AsyncApp  # noqa: PLC0415

        app = AsyncApp()

        @app.event("message")  # type: ignore[untyped-decorator]
        async def _on_message(event: dict[str, object]) -> None:
            channel = str(event.get("channel", ""))
            text = str(event.get("text", ""))
            if channel and text:
                await self.handle_event(channel, text)

        @app.event("app_mention")  # type: ignore[untyped-decorator]
        async def _on_app_mention(event: dict[str, object]) -> None:
            channel = str(event.get("channel", ""))
            text = str(event.get("text", ""))
            if channel and text:
                await self.handle_event(channel, text)

        AsyncSlackRequestHandler(app)


_AdapterFactory = Callable[[], Awaitable[None]]


__all__ = ["SlackChatAdapter"]
