"""Tests for `record_llm` + `MockLLMClient.from_recording` (feat-016 chunk 3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentforge.testing import MockLLMClient, load_recording, record_llm
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.messages import Message


@pytest.mark.asyncio
async def test_record_writes_header_and_entries(tmp_path: Path) -> None:
    real = MockLLMClient.from_script(
        [{"text": "first"}, {"text": "second", "stop_reason": "end_turn"}]
    )
    target = tmp_path / "cassette.jsonl"
    wrapped = record_llm(real, target)

    await wrapped.call(system="", messages=[Message(role="user", content="hi")])
    await wrapped.call(system="", messages=[])
    await wrapped.close()

    text = target.read_text(encoding="utf-8").strip().splitlines()
    assert len(text) == 3, text  # header + two records
    header = json.loads(text[0])
    assert header["format_version"] == 1
    assert "api_key" in header["redactions"]
    first_record = json.loads(text[1])
    assert first_record["response"]["content"] == "first"


@pytest.mark.asyncio
async def test_replay_from_recording_matches_responses(tmp_path: Path) -> None:
    real = MockLLMClient.from_script([{"text": "rec1"}, {"text": "rec2"}])
    cassette = tmp_path / "cassette.jsonl"
    wrapped = record_llm(real, cassette)
    await wrapped.call(system="", messages=[])
    await wrapped.call(system="", messages=[])

    replay = MockLLMClient.from_recording(str(cassette))
    out1 = await replay.call(system="", messages=[])
    out2 = await replay.call(system="", messages=[])
    assert out1.content == "rec1"
    assert out2.content == "rec2"


def test_redact_replaces_sensitive_keys_recursively() -> None:
    """Unit-test the redaction helper directly — recordings exercise
    the integration via _RecordingLLMClient.call."""
    from agentforge.testing.recording import _redact  # noqa: PLC0415

    payload = {
        "api_key": "secret",
        "nested": {"Authorization": "Bearer x", "keep": "ok"},
        "items": [{"api_key": "another"}, {"trace": "ok"}],
    }
    out = _redact(payload, ("api_key", "authorization", "bearer"))
    assert out["api_key"] == "<redacted>"
    assert out["nested"]["Authorization"] == "<redacted>"
    assert out["nested"]["keep"] == "ok"
    assert out["items"][0]["api_key"] == "<redacted>"
    assert out["items"][1]["trace"] == "ok"


def test_load_recording_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(ModuleError, match="does not exist"):
        load_recording(tmp_path / "no.jsonl")


def test_load_recording_unsupported_version(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"format_version": 999, "redactions": []}) + "\n", encoding="utf-8")
    with pytest.raises(ModuleError, match="not supported"):
        load_recording(bad)
