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

ChatChunkKind = Literal["text", "tool_call", "tool_result", "thinking", "done", "error"]
"""Closed enum of streaming chunk kinds. Adding a new kind requires a
minor version bump per ADR-0007. Receivers must ignore unknown kinds
on the wire — forward-compat for future additions."""


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
