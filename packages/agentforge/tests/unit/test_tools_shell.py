"""Unit tests for `ShellTool` / `shell` (feat-004 chunk 3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from agentforge.tools import ShellTool
from pydantic import ValidationError


@pytest.mark.asyncio
async def test_runs_simple_command(tmp_path: Path) -> None:
    tool = ShellTool(work_dir=tmp_path)
    out = await tool.run(command=[sys.executable, "-c", "print('hello')"])
    assert "hello" in out


@pytest.mark.asyncio
async def test_captures_stderr_in_combined_output(tmp_path: Path) -> None:
    tool = ShellTool(work_dir=tmp_path)
    out = await tool.run(
        command=[
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('oops\\n'); sys.exit(1)",
        ]
    )
    assert "[exit 1]" in out
    assert "oops" in out


@pytest.mark.asyncio
async def test_runs_in_work_dir(tmp_path: Path) -> None:
    """The subprocess sees `tmp_path` as its CWD."""
    (tmp_path / "marker.txt").write_text("here", encoding="utf-8")
    tool = ShellTool(work_dir=tmp_path)
    out = await tool.run(
        command=[sys.executable, "-c", "import os; print(os.path.exists('marker.txt'))"]
    )
    assert "True" in out


@pytest.mark.asyncio
async def test_no_shell_interpretation(tmp_path: Path) -> None:
    """`shell=False` semantics: argv is a list, no `;` chaining,
    no shell-injection vector. The dangerous-looking string is
    passed as a literal argv element, not interpreted by a shell."""
    tool = ShellTool(work_dir=tmp_path)
    # The python interpreter prints repr of its argv[1] — proving
    # that `'; echo HACKED'` reached the program as ONE literal
    # argument, not two commands chained by a shell.
    out = await tool.run(
        command=[sys.executable, "-c", "import sys; print(repr(sys.argv[1]))", "; echo HACKED"]
    )
    # Repr-quoted form proves it was a single argv element.
    assert "'; echo HACKED'" in out


@pytest.mark.asyncio
async def test_timeout_kills_process(tmp_path: Path) -> None:
    tool = ShellTool(work_dir=tmp_path, timeout_s=0.5)
    with pytest.raises(TimeoutError, match="timeout_s"):
        await tool.run(command=[sys.executable, "-c", "import time; time.sleep(5)"])


@pytest.mark.asyncio
async def test_allowed_commands_whitelist(tmp_path: Path) -> None:
    tool = ShellTool(work_dir=tmp_path, allowed_commands=("python", "ls"))
    with pytest.raises(ValueError, match="not in allowed_commands"):
        await tool.run(command=["rm", "-rf", "/"])


@pytest.mark.asyncio
async def test_allowed_commands_permits_listed(tmp_path: Path) -> None:
    tool = ShellTool(work_dir=tmp_path, allowed_commands=(sys.executable,))
    # Should NOT raise — argv[0] is in the whitelist.
    await tool.run(command=[sys.executable, "-c", "print('ok')"])


@pytest.mark.asyncio
async def test_output_truncation(tmp_path: Path) -> None:
    tool = ShellTool(work_dir=tmp_path, max_output_bytes=100)
    out = await tool.run(command=[sys.executable, "-c", "print('x' * 1000)"])
    assert "[output truncated]" in out
    assert len(out) < 1000


# ---- Constructor validation ----


def test_constructor_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        ShellTool(timeout_s=0)


def test_constructor_rejects_negative_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        ShellTool(timeout_s=-1)


def test_constructor_rejects_non_directory(tmp_path: Path) -> None:
    f = tmp_path / "f.txt"
    f.write_text("x")
    with pytest.raises(ValueError, match="not a directory"):
        ShellTool(work_dir=f)


def test_constructor_rejects_zero_max_output() -> None:
    with pytest.raises(ValueError, match="max_output_bytes"):
        ShellTool(max_output_bytes=0)


# ---- Tool surface ----


def test_capabilities_declared(tmp_path: Path) -> None:
    tool = ShellTool(work_dir=tmp_path)
    assert tool.capabilities == frozenset({"shell", "destructive"})


def test_input_schema_requires_non_empty_command(tmp_path: Path) -> None:
    tool = ShellTool(work_dir=tmp_path)
    with pytest.raises(ValidationError):
        tool.input_schema.model_validate({"command": []})
