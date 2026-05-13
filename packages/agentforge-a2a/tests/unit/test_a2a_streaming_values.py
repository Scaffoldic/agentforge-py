"""Unit tests for the A2A streaming wire format (feat-014 v0.2 follow-up)."""

from __future__ import annotations

import asyncio

import pytest
from agentforge_a2a import A2AChunk
from agentforge_a2a._inmem_runner import FakeA2AClientRunner
from pydantic import ValidationError


def test_a2a_chunk_is_frozen_and_validates_kind() -> None:
    chunk = A2AChunk(kind="step", step={"iteration": 0, "kind": "think", "content": "x"})
    assert chunk.kind == "step"
    with pytest.raises(ValidationError):
        chunk.kind = "done"  # type: ignore[misc]


def test_a2a_chunk_accepts_unified_streaming_kinds() -> None:
    """v0.3 unifies A2AChunkKind with StreamingChunkKind, so per-token
    `text` / `thinking` kinds are now valid on the A2A wire."""
    for kind in ("text", "thinking", "step", "tool_call", "tool_result", "done", "error"):
        chunk = A2AChunk(kind=kind, content="x" if kind in {"text", "thinking"} else {"x": 1})
        assert chunk.kind == kind


def test_a2a_chunk_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        A2AChunk(kind="bogus")  # type: ignore[arg-type]


def test_a2a_chunk_done_carries_content() -> None:
    chunk = A2AChunk(
        kind="done", content={"output": "ok", "cost_usd": 0.0}, run_id="r", parent_run_id="p"
    )
    assert chunk.content == {"output": "ok", "cost_usd": 0.0}
    assert chunk.run_id == "r"
    assert chunk.parent_run_id == "p"


def test_fake_runner_post_stream_yields_configured_chunks() -> None:
    runner = FakeA2AClientRunner(
        responses_stream=[
            {"kind": "step", "step": {"iteration": 0, "kind": "think", "content": "a"}},
            {"kind": "step", "step": {"iteration": 1, "kind": "act", "content": "b"}},
            {"kind": "done", "content": {"output": "ok"}},
        ]
    )

    async def _collect() -> list[dict[str, object]]:
        return [
            chunk
            async for chunk in runner.post_stream(
                "https://x/a2a/v1/calls/stream",
                headers={"Authorization": "Bearer t"},
                json={"endpoint": "verify", "payload": {}, "budget_usd": None},
                ssl_context=None,
                timeout_s=5.0,
            )
        ]

    chunks = asyncio.run(_collect())
    assert [c["kind"] for c in chunks] == ["step", "step", "done"]
    assert runner.stream_calls[0].url == "https://x/a2a/v1/calls/stream"


def test_fake_runner_post_stream_raises_configured_error() -> None:
    runner = FakeA2AClientRunner()
    runner.set_error(RuntimeError("boom"))

    async def _drain() -> None:
        async for _ in runner.post_stream(
            "https://x", headers={}, json={}, ssl_context=None, timeout_s=1.0
        ):
            pass

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(_drain())
