"""Unit tests for `FileReadTool` / `file_read` (feat-004 chunk 2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge.tools import FileReadTool


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """Build a temp directory with a few files for the tool to read."""
    (tmp_path / "hello.txt").write_text("hello world", encoding="utf-8")
    (tmp_path / "big.txt").write_text("x" * 1000, encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "inner.txt").write_text("inside", encoding="utf-8")
    return tmp_path


@pytest.mark.asyncio
async def test_reads_file_in_sandbox(sandbox: Path) -> None:
    tool = FileReadTool(work_dir=sandbox)
    assert await tool.run(path="hello.txt") == "hello world"


@pytest.mark.asyncio
async def test_reads_nested_path(sandbox: Path) -> None:
    tool = FileReadTool(work_dir=sandbox)
    assert await tool.run(path="nested/inner.txt") == "inside"


@pytest.mark.asyncio
async def test_rejects_absolute_path(sandbox: Path) -> None:
    tool = FileReadTool(work_dir=sandbox)
    with pytest.raises(ValueError, match="absolute paths"):
        await tool.run(path=str(sandbox / "hello.txt"))


@pytest.mark.asyncio
async def test_rejects_dotdot_traversal(sandbox: Path) -> None:
    """`../` resolution must fail the contained-path check."""
    tool = FileReadTool(work_dir=sandbox)
    with pytest.raises(ValueError, match="outside the sandbox"):
        await tool.run(path="../etc/passwd")


@pytest.mark.asyncio
async def test_rejects_path_to_directory(sandbox: Path) -> None:
    tool = FileReadTool(work_dir=sandbox)
    with pytest.raises(ValueError, match="not a file"):
        await tool.run(path="nested")


@pytest.mark.asyncio
async def test_rejects_missing_file(sandbox: Path) -> None:
    tool = FileReadTool(work_dir=sandbox)
    with pytest.raises(ValueError, match="not a file"):
        await tool.run(path="ghost.txt")


@pytest.mark.asyncio
async def test_size_cap_blocks_large_files(sandbox: Path) -> None:
    tool = FileReadTool(work_dir=sandbox, max_bytes=500)
    with pytest.raises(ValueError, match="max_bytes"):
        await tool.run(path="big.txt")


@pytest.mark.asyncio
async def test_size_cap_allows_files_under_limit(sandbox: Path) -> None:
    tool = FileReadTool(work_dir=sandbox, max_bytes=2000)
    content = await tool.run(path="big.txt")
    assert len(content) == 1000


# ---- Constructor validation ----


def test_constructor_rejects_zero_max_bytes() -> None:
    with pytest.raises(ValueError, match="max_bytes"):
        FileReadTool(max_bytes=0)


def test_constructor_rejects_negative_max_bytes() -> None:
    with pytest.raises(ValueError, match="max_bytes"):
        FileReadTool(max_bytes=-1)


def test_constructor_rejects_non_directory(tmp_path: Path) -> None:
    file = tmp_path / "f.txt"
    file.write_text("x")
    with pytest.raises(ValueError, match="not a directory"):
        FileReadTool(work_dir=file)


# ---- Tool surface ----


def test_tool_metadata(sandbox: Path) -> None:
    tool = FileReadTool(work_dir=sandbox)
    assert tool.name == "file_read"
    assert "filesystem" in tool.capabilities
    assert "path" in tool.input_schema.model_json_schema()["properties"]
