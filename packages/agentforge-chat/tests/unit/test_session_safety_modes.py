"""Tests for `ChatSession.safety_mode` dispatch (feat-020 v0.3 polish).

Exercises the three safety modes against a streaming strategy:

- ``"buffer-then-stream"`` (default) — per-token text passes
  through unbuffered; terminal `check_output` runs once.
- ``"sentence-window"`` — text accumulates in
  `_SentenceWindowBuffer`; each completed sentence runs through
  `check_output` before being emitted as a `text` chunk.
- ``"stream-then-redact"`` — current alias for
  ``sentence-window``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from agentforge.agent import Agent
from agentforge_chat import ChatSession, InMemoryChatHistory
from agentforge_core.contracts.guardrails import OutputValidator
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.chat import StreamingEvent
from agentforge_core.values.guardrails import ValidationResult
from agentforge_core.values.messages import LLMResponse, Message, TokenUsage, ToolSpec
from agentforge_core.values.state import AgentState, Step


class _FakeLLM(LLMClient):
    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        del system, messages, tools
        return LLMResponse(
            content="",
            tool_calls=(),
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=0, output_tokens=0),
            cost_usd=0.0,
            model="fake",
            provider="fake",
        )

    async def close(self) -> None:
        return None


class _StreamingStrategy(ReasoningStrategy):
    """Streams a fixed transcript token-by-token via per-text events.

    The transcript contains ``sk-SECRET`` so output-validator tests
    can verify the value is redacted in sentence-window mode.
    """

    _TOKENS = (
        "My ",
        "key ",
        "is ",
        "sk-SECRET",
        ". ",
        "Don't ",
        "share ",
        "it",
        ". ",
        "Goodbye",
        ".",
    )

    async def run(self, state: AgentState) -> AgentState:
        text = "".join(self._TOKENS)
        state.steps.append(Step(iteration=0, kind="synthesize", content=text, cost_usd=0.0))
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        for token in self._TOKENS:
            yield StreamingEvent(kind="text", content=token, metadata={})
        # `Agent.stream` wraps this with the canonical `done` event;
        # don't need to emit our own.


class _SecretRedactor(OutputValidator):
    """Replaces `sk-SECRET` with `<redacted>` in any output text."""

    name = "secret-redactor"
    description = "Test redactor for the sk-SECRET token (feat-020 v0.3)."

    async def validate(self, content: str, context: dict[str, Any]) -> ValidationResult:
        del context
        if "sk-SECRET" in content:
            return ValidationResult(
                passed=False,
                violations=("secret_token",),
                redacted_content=content.replace("sk-SECRET", "<redacted>"),
            )
        return ValidationResult(passed=True)


def _agent_with_redactor() -> Agent:
    return Agent(
        model=_FakeLLM(),
        strategy=_StreamingStrategy(),
        output_validators=[_SecretRedactor()],
    )


@pytest.mark.asyncio
async def test_default_safety_mode_is_buffer_then_stream() -> None:
    session = ChatSession(_agent_with_redactor(), history_store=InMemoryChatHistory())
    assert session._safety_mode == "buffer-then-stream"


@pytest.mark.asyncio
async def test_sentence_window_redacts_per_sentence() -> None:
    """Sentence-window mode runs `check_output` per completed
    sentence; the secret is masked BEFORE any chunk reaches the
    wire."""
    session = ChatSession(
        _agent_with_redactor(),
        history_store=InMemoryChatHistory(),
        safety_mode="sentence-window",
    )
    chunks = [chunk async for chunk in await session.stream("anything")]
    text_chunks = [c for c in chunks if c.kind == "text"]
    # All emitted text chunks have the secret masked.
    for chunk in text_chunks:
        assert "sk-SECRET" not in str(chunk.content)
    # At least one chunk contains the redaction marker.
    assert any("<redacted>" in str(c.content) for c in text_chunks)
    # Stream still terminates with a `done` chunk.
    assert chunks[-1].kind == "done"


@pytest.mark.asyncio
async def test_buffer_then_stream_still_redacts_at_end() -> None:
    """The default `buffer-then-stream` path forwards raw token
    chunks (no per-token redaction) but the persisted assistant
    turn is redacted by the terminal `check_output`."""
    session = ChatSession(
        _agent_with_redactor(),
        history_store=InMemoryChatHistory(),
        safety_mode="buffer-then-stream",
    )
    chunks = [chunk async for chunk in await session.stream("anything")]
    # Per-token forwarding means the secret CAN appear in
    # individual text chunks (this is the trade-off this mode
    # makes). Sentence-window is the safer alternative.
    text_chunks = [c for c in chunks if c.kind == "text"]
    raw_seen = any("sk-SECRET" in str(c.content) for c in text_chunks)
    assert raw_seen
    # But the persisted assistant turn is redacted.
    history = await session.history(roles=["assistant"])
    assert all("sk-SECRET" not in t.content for t in history)


@pytest.mark.asyncio
async def test_stream_then_redact_aliases_sentence_window() -> None:
    """`stream-then-redact` currently behaves identically to
    `sentence-window`."""
    session = ChatSession(
        _agent_with_redactor(),
        history_store=InMemoryChatHistory(),
        safety_mode="stream-then-redact",
    )
    chunks = [chunk async for chunk in await session.stream("anything")]
    text_chunks = [c for c in chunks if c.kind == "text"]
    for chunk in text_chunks:
        assert "sk-SECRET" not in str(chunk.content)
