"""Chat-agent value types (feat-020).

Frozen Pydantic models that ride the wire between `ChatSession`,
`ChatHistoryStore` drivers, and the chat-http server.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agentforge_core.values.messages import ToolCall

ChatRole = Literal["user", "assistant", "system", "tool"]
"""Closed enum of chat turn roles."""

StreamingChunkKind = Literal[
    "text",
    "thinking",
    "step",
    "tool_call",
    "tool_result",
    "done",
    "error",
]
"""Closed enum of streaming chunk kinds shared across chat (token-level)
and A2A (step + token-level) wire formats. Adding a new kind requires a
minor version bump per ADR-0007. Receivers must ignore unknown kinds on
the wire — forward-compat for future additions.

The ``step`` kind is reserved for strategies that emit step-level
events alongside (or instead of) per-token text. Chat receivers
typically ignore it; A2A clients render it as a generic step boundary.
"""

ChatChunkKind = StreamingChunkKind
"""Backward-compatible alias retained for callers that imported the
chat-shaped name in feat-020 v0.1 / v0.2. Prefer ``StreamingChunkKind``
in new code."""


class ChatTurn(BaseModel):
    """One persisted message in a chat session.

    Stored by `ChatHistoryStore` drivers, surfaced through
    `ChatSession.history()`, and emitted on the chat-http wire.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    id: str
    session_id: str
    role: ChatRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str | None = None
    """Links assistant turns (and the tool turns produced inside them)
    back to the AgentForge run that emitted them. None for user /
    system turns."""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionInfo(BaseModel):
    """Session-level metadata returned by `list_sessions` /
    `delete_session` / `update_session_metadata`."""

    model_config = ConfigDict(frozen=True, strict=True)

    id: str
    owner: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_active_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    turn_count: int = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatChunk(BaseModel):
    """One streaming chunk emitted by `ChatSession.stream()` /
    `ChatServer` SSE+WS."""

    model_config = ConfigDict(frozen=True, strict=True)

    kind: ChatChunkKind
    content: str | dict[str, Any] | None = None
    cumulative_text: str | None = None
    turn_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Aggregated response returned by `ChatSession.send()`."""

    model_config = ConfigDict(frozen=True, strict=True)

    content: str
    turn_id: str
    run_id: str
    tool_calls: tuple[ToolCall, ...] = ()
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    duration_ms: int = Field(default=0, ge=0)
    finish_reason: str = "completed"


class StreamingEvent(BaseModel):
    """One event emitted by `ReasoningStrategy.stream()` (feat-020 v0.2).

    Strategies that want per-token streaming override the default
    `stream()` to yield these events as the LLM emits tokens / step
    transitions. `ChatSession.stream()` forwards each event to a
    `ChatChunk` on the wire (kinds map 1:1 with `ChatChunkKind`).
    The default base-class `stream()` calls `run()` and yields a
    single `done` event so existing concrete strategies keep
    working unchanged.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    kind: ChatChunkKind
    content: str | dict[str, Any] | None = None
    cumulative_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
