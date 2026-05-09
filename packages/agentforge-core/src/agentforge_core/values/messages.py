"""Provider-agnostic message and response shapes for the LLM contract.

Every `LLMClient` returns `LLMResponse`; every reasoning strategy
operates on `list[Message]` regardless of which provider backs the
agent. Streaming clients yield `StreamChunk`s; embedding clients
return `EmbeddingResponse`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StreamChunkKind = Literal["text", "tool_call", "stop", "thinking"]
"""Closed enum of stream-chunk kinds. Provider drivers normalise their
event streams into a sequence of these chunks. Adding a new kind is a
minor version bump."""

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


class StreamChunk(BaseModel):
    """One event in a provider's streaming response.

    Streaming `LLMClient`s yield an `AsyncIterator[StreamChunk]`. The
    chunks are ordered: text deltas, optional thinking blocks, optional
    tool-call deltas, and exactly one terminal `stop` chunk carrying
    the final usage and cost. Consumers that don't care about
    streaming can accumulate chunks into a single `LLMResponse` via
    a helper.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    kind: StreamChunkKind
    delta: str = ""
    """Incremental content for `text` and `thinking` kinds (empty for
    `tool_call` and `stop`)."""

    tool_call: ToolCall | None = None
    """The fully-assembled `ToolCall` for `kind == "tool_call"` chunks.
    Provider drivers buffer tool-call argument streams internally and
    emit one chunk once the call is complete."""

    stop_reason: StopReason | None = None
    """Set on the terminal `stop` chunk; `None` otherwise."""

    usage: TokenUsage | None = None
    """Final token accounting on the terminal `stop` chunk."""

    cost_usd: float = Field(default=0.0, ge=0.0)
    """Final cost on the terminal `stop` chunk; `0.0` on intermediate
    chunks."""


class EmbeddingResponse(BaseModel):
    """Provider-agnostic response from an embedding call.

    `vectors` is a list of float lists — one vector per input text in
    the same order the texts were passed. Every vector has the same
    `dimensions` (the model-declared dimensionality).
    """

    model_config = ConfigDict(frozen=True, strict=True)

    vectors: tuple[tuple[float, ...], ...]
    """One vector per input text, in input order. Tuples-of-tuples
    keeps the response frozen and hashable while the dimensionality
    stays uniform across vectors."""

    dimensions: int = Field(ge=1)
    """Length of every vector. The `EmbeddingClient.dimensions()`
    accessor declares this up front for callers that need to size
    storage before the call."""

    usage: TokenUsage
    """Token accounting (input only — embeddings produce no output
    tokens)."""

    cost_usd: float = Field(ge=0.0)
    model: str
    provider: str
