"""Unit tests for the `LLMClient` ABC."""

from __future__ import annotations

import pytest
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.values.messages import LLMResponse, Message, TokenUsage, ToolSpec


def test_llmclient_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError, match="abstract"):
        LLMClient()  # type: ignore[abstract]


class _MinimalClient(LLMClient):
    """Minimal subclass overriding every abstract method."""

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            content="ok",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=1, output_tokens=1),
            cost_usd=0.0,
            model="m",
            provider="p",
        )

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_minimal_subclass_works() -> None:
    client = _MinimalClient()
    response = await client.call("sys", [Message(role="user", content="hi")])
    assert response.content == "ok"
    await client.close()


def test_default_capabilities_is_empty() -> None:
    assert _MinimalClient().capabilities() == set()


def test_supports_returns_false_for_unknown_capability() -> None:
    assert _MinimalClient().supports("caching") is False


class _CachingClient(_MinimalClient):
    def capabilities(self) -> set[str]:
        return {"caching", "streaming"}


def test_supports_returns_true_for_declared_capability() -> None:
    client = _CachingClient()
    assert client.supports("caching") is True
    assert client.supports("streaming") is True
    assert client.supports("thinking") is False
