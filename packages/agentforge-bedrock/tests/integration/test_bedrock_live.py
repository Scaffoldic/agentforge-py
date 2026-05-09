"""Live integration tests against AWS Bedrock.

Skipped unless `RUN_LIVE_BEDROCK=1` is set in the environment. The
default boto3 credential chain (`~/.aws/credentials`, env vars, IAM
role) is used — no creds are baked into the test code.

Test default model: cross-region Haiku (`us.anthropic.claude-haiku-4-5-...`)
because:
  - it's the cheapest Anthropic model on Bedrock
  - the cross-region profile smooths out throttling on shared regions
  - it's available in every commercial-region account once any Anthropic
    model has been used in the account (per AWS's auto-enablement)

Override via the `BEDROCK_TEST_MODEL` env var, e.g.:

    RUN_LIVE_BEDROCK=1 BEDROCK_TEST_MODEL=global.anthropic.claude-sonnet-4-5-20250929-v1:0 \
        uv run pytest packages/agentforge-bedrock/tests/integration -v
"""

from __future__ import annotations

import os

import pytest
from agentforge_bedrock import BedrockClient
from agentforge_core.values.messages import Message

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_BEDROCK") != "1",
    reason="Set RUN_LIVE_BEDROCK=1 to run live Bedrock tests.",
)

_DEFAULT_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def _model_id() -> str:
    return os.environ.get("BEDROCK_TEST_MODEL", _DEFAULT_MODEL)


@pytest.mark.asyncio
async def test_live_bedrock_call_returns_real_response() -> None:
    """Smoke test: real Bedrock call, real cost, real tokens."""
    client = BedrockClient(model_id=_model_id())
    try:
        resp = await client.call(
            "Be very brief.",
            [Message(role="user", content="Say only the word 'pong'.")],
        )
    finally:
        await client.close()

    assert resp.content
    assert resp.usage.input_tokens > 0
    assert resp.usage.output_tokens > 0
    assert resp.cost_usd >= 0  # may be 0.0 if model not in price table
    assert resp.provider == "bedrock"
    assert resp.model == _model_id()
    assert resp.stop_reason in {"end_turn", "max_tokens", "stop_sequence", "other"}


@pytest.mark.asyncio
async def test_live_bedrock_call_supports_multi_turn() -> None:
    client = BedrockClient(model_id=_model_id())
    try:
        resp = await client.call(
            "You answer in single words.",
            [
                Message(role="user", content="What is 2+2?"),
                Message(role="assistant", content="4"),
                Message(role="user", content="And 3+3?"),
            ],
        )
    finally:
        await client.close()
    # Loose check — model output varies; we just need a non-empty answer.
    assert resp.content.strip()
