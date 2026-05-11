"""Tests for `analyze_recording` (feat-016 chunk 4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge.testing import MockLLMClient, record_llm
from agentforge_testing.analysis import analyze_recording


@pytest.mark.asyncio
async def test_analyze_recording_aggregates_stats(tmp_path: Path) -> None:
    real = MockLLMClient.from_script(
        [
            {
                "text": "first",
                "tool_calls": [{"name": "search", "args": {"q": "x"}}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "cost_usd": 0.001,
            },
            {
                "text": "second",
                "usage": {"input_tokens": 8, "output_tokens": 3},
                "cost_usd": 0.0005,
                "stop_reason": "end_turn",
            },
        ]
    )
    cassette = tmp_path / "cassette.jsonl"
    wrapped = record_llm(real, cassette)
    await wrapped.call(system="", messages=[])
    await wrapped.call(system="", messages=[])

    stats = analyze_recording(cassette)
    assert stats.call_count == 2
    assert stats.tokens_in == 18
    assert stats.tokens_out == 8
    assert stats.cost_usd == pytest.approx(0.0015)
    assert stats.tool_call_names == {"search": 1}
    assert "api_key" in stats.redactions
