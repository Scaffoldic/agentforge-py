"""Tests for `agentforge health` (feat-017 chunk 8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentforge.cli.main import main


def _write_cfg(tmp_path: Path, body: str) -> Path:
    cfg = tmp_path / "agentforge.yaml"
    cfg.write_text(body, encoding="utf-8")
    return cfg


def test_health_minimal_config_is_ok(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_cfg(tmp_path, "agent: {}\n")
    code = main(["health", "--path", str(cfg)])
    out = capsys.readouterr().out
    assert code == 0
    assert "OK" in out
    assert "config" in out


def test_health_invalid_config_returns_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_cfg(tmp_path, "agent:\n  budget:\n    usd: -1\n")
    code = main(["health", "--path", str(cfg)])
    out = capsys.readouterr().out
    assert code == 2
    assert "FAIL" in out


def test_health_json_output_shape(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_cfg(tmp_path, "agent: {}\n")
    code = main(["health", "--path", str(cfg), "--output-format", "json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["ok"] is True
    assert isinstance(payload["checks"], list)
    assert any(c["kind"] == "config" for c in payload["checks"])
