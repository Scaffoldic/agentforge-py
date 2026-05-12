"""`FakeSlackRunner` for unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _Message:
    channel: str
    ts: str
    text: str


@dataclass
class FakeSlackRunner:
    """Records `post_message` / `update_message` calls."""

    posted: list[_Message] = field(default_factory=list)
    updates: list[_Message] = field(default_factory=list)
    _counter: int = 0

    async def post_message(self, channel: str, text: str) -> str:
        self._counter += 1
        ts = f"ts-{self._counter}"
        self.posted.append(_Message(channel=channel, ts=ts, text=text))
        return ts

    async def update_message(self, channel: str, ts: str, text: str) -> None:
        self.updates.append(_Message(channel=channel, ts=ts, text=text))


__all__ = ["FakeSlackRunner"]
