"""Integration test — Agent + BedrockClient + ReActLoop end-to-end.

This is the cross-package integration: the Agent orchestrator
constructs a Bedrock client from a `"bedrock:..."` model string,
the ReAct loop drives the conversation, the fake AWS session
returns a scripted Converse response, and we assert the final
RunResult shape.

No live AWS credentials are touched — the fake session injects a
canned Bedrock response directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from agentforge import Agent
from agentforge_bedrock import BedrockClient


class _FakeBedrockClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self._response


class _FakeSession:
    def __init__(self, fake_client: _FakeBedrockClient) -> None:
        self._fake_client = fake_client

    def client(self, _service: str, **_kwargs: Any) -> Any:
        @asynccontextmanager
        async def _cm() -> AsyncIterator[_FakeBedrockClient]:
            yield self._fake_client

        return _cm()


@pytest.mark.asyncio
async def test_agent_runs_react_over_bedrock_via_typed_client() -> None:
    """Pass a typed BedrockClient with an injected fake session
    directly to Agent — exercises the full happy path through
    the ReAct loop and Bedrock response normalisation."""
    fake = _FakeBedrockClient(
        response={
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "the answer is 42"}],
                }
            },
            "stopReason": "end_turn",
            "usage": {"inputTokens": 8, "outputTokens": 5, "totalTokens": 13},
        }
    )
    session = _FakeSession(fake)
    bedrock = BedrockClient(model_id="anthropic.claude-3-haiku-20240307-v1:0", session=session)

    async with Agent(
        model=bedrock,
        strategy="react",
        budget_usd=2.0,
        install_log_filter=False,
    ) as agent:
        result = await agent.run("Compute 6 * 7.")

    assert result.output == "the answer is 42"
    assert result.finish_reason == "completed"
    # The Bedrock client got exactly one Converse call.
    assert len(fake.calls) == 1
    sent = fake.calls[0]
    assert sent["modelId"] == "anthropic.claude-3-haiku-20240307-v1:0"
    # User task makes it into the messages array.
    user_text = sent["messages"][0]["content"][0]["text"]
    assert "6 * 7" in user_text


@pytest.mark.asyncio
async def test_agent_resolves_bedrock_string_via_resolver() -> None:
    """`Agent(model="bedrock:<model-id>")` resolves the bedrock
    provider through the registry. We can't pass a session into the
    auto-resolved client, so we just verify it constructs without
    raising — credentials are NOT touched at construction time."""
    async with Agent(
        model="bedrock:anthropic.claude-3-haiku-20240307-v1:0",
        strategy="react",
        budget_usd=2.0,
        install_log_filter=False,
    ) as agent:
        assert isinstance(agent._llm, BedrockClient)
        assert agent._llm._model_id == "anthropic.claude-3-haiku-20240307-v1:0"
