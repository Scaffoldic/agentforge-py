"""Internal Slack-runner abstraction.

`SlackChatAdapter` goes through one of these for every API call.
Unit tests inject a `FakeSlackRunner` from `_inmem_runner.py`.
"""

from __future__ import annotations

from typing import Any, Protocol


class SlackRunner(Protocol):  # pragma: no cover — Protocol stubs
    """Thin slice of `slack_sdk.web.async_client.AsyncWebClient`."""

    async def post_message(self, channel: str, text: str) -> str:
        """Post ``text`` to ``channel``; return the ts of the new message."""

    async def update_message(self, channel: str, ts: str, text: str) -> None:
        """Edit message at ``(channel, ts)`` to ``text``."""


class _BoltClientRunner:  # pragma: no cover — exercised only with `-m live`
    """Production runner wrapping `slack_sdk.web.async_client.AsyncWebClient`."""

    def __init__(self, client: Any) -> None:
        self._c = client

    async def post_message(self, channel: str, text: str) -> str:
        response = await self._c.chat_postMessage(channel=channel, text=text)
        return str(response.get("ts", ""))

    async def update_message(self, channel: str, ts: str, text: str) -> None:
        await self._c.chat_update(channel=channel, ts=ts, text=text)


__all__ = ["SlackRunner"]
