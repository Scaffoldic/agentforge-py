"""Tests for `agentforge debug` (feat-017 chunk 6)."""

from __future__ import annotations

import io
from typing import Any

import pytest
from agentforge.cli.debug_cmd import _ReplayREPL


def _steps() -> list[dict[str, Any]]:
    return [
        {"iteration": 0, "kind": "think", "content": "reasoning A"},
        {
            "iteration": 0,
            "kind": "act",
            "content": {"call": "echo"},
            "tool_call": {"id": "t1", "name": "echo", "arguments": {"text": "hi"}},
        },
        {"iteration": 0, "kind": "observe", "content": "recorded: hi"},
    ]


def _run_repl(script: str) -> str:
    out = io.StringIO()
    repl = _ReplayREPL(_steps(), stdin=io.StringIO(script + "\n"), stdout=out)
    repl.use_rawinput = False
    repl.cmdloop()
    return out.getvalue()


def test_repl_step_advances_cursor() -> None:
    out = _run_repl("step\nstep\nquit")
    assert "kind=think" in out
    assert "kind=act" in out


def test_repl_state_after_step_prints_payload() -> None:
    out = _run_repl("step\nstate\nquit")
    assert '"reasoning A"' in out


def test_repl_inspect_supports_dotted_path() -> None:
    out = _run_repl("step\nstep\ninspect tool_call.name\nquit")
    assert "echo" in out


def test_repl_steps_lists_all_steps() -> None:
    out = _run_repl("steps\nquit")
    assert "think" in out
    assert "act" in out
    assert "observe" in out


def test_repl_back_then_state_shows_prior_step() -> None:
    out = _run_repl("step\nstep\nback\nstate\nquit")
    assert '"reasoning A"' in out


@pytest.mark.parametrize("alias", ["q", "quit"])
def test_repl_quit_aliases_exit(alias: str) -> None:
    # Just exercise the quit aliases without raising.
    _run_repl(alias)
