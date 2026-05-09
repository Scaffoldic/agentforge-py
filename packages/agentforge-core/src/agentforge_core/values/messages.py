"""Provider-agnostic message and response shapes for the LLM contract.

Every `LLMClient` (feat-003) returns `LLMResponse`; every reasoning
strategy operates on `list[Message]` regardless of which provider
backs the agent.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["system", "user", "assistant", "tool"]
"""Allowed message roles. Mirrors the Anthropic / OpenAI common set."""

StopReason = Literal["end_turn", "tool_use", "max_tokens", "stop_sequence", "other"]
"""Provider-normalised reason the LLM stopped emitting tokens."""


class Message(BaseModel):
    """One turn in the chat-completion exchange."""

    model_config = ConfigDict(frozen=True, strict=True)

    role: MessageRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None


class ToolCall(BaseModel):
    """A tool invocation emitted by the LLM."""

    model_config = ConfigDict(frozen=True, strict=True)

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolSpec(BaseModel):
    """Provider-agnostic tool description sent to the LLM.

    `schema` is the JSON-schema dict (typically from a Pydantic model's
    `model_json_schema()`). The `Tool` ABC's `to_spec()` produces this.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    name: str
    description: str
    schema_: dict[str, Any] = Field(alias="schema")


class TokenUsage(BaseModel):
    """Token accounting from a single LLM call."""

    model_config = ConfigDict(frozen=True, strict=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    thinking_tokens: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        """Sum of input + output tokens (excludes cache and thinking metadata)."""
        return self.input_tokens + self.output_tokens


class LLMResponse(BaseModel):
    """Provider-agnostic response from one LLM call."""

    model_config = ConfigDict(frozen=True, strict=True)

    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    stop_reason: StopReason
    usage: TokenUsage
    cost_usd: float = Field(ge=0.0)
    model: str
    provider: str
