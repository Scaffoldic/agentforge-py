"""`file_read` — sandboxed file-reading tool (feat-004).

Reads a file from a configurable working directory with a size cap.
The default instance is sandboxed to the process's current working
directory at import time and caps reads at 1 MiB; users who want
different limits construct their own:

    custom = FileReadTool(work_dir="/srv/data", max_bytes=10 * 1024 * 1024)
    agent = Agent(tools=[custom, ...])

Sandbox enforcement:
  - Path is resolved against `work_dir` then checked: the resolved
    real path must be inside `work_dir` (no `../` escape, no
    absolute paths that escape the sandbox).
  - Symlinks are followed, but the target must also be inside the
    sandbox.
  - Files larger than `max_bytes` raise `ValueError` before reading.

Capabilities: `{"filesystem"}`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from agentforge_core.contracts.tool import Tool
from pydantic import BaseModel, Field

_DEFAULT_MAX_BYTES = 1 * 1024 * 1024  # 1 MiB


class _FileReadInput(BaseModel):
    """Input schema for `file_read`."""

    path: str = Field(
        description=(
            "Relative path inside the sandbox to read. "
            "Absolute paths and `..` traversal are rejected."
        )
    )


class FileReadTool(Tool):
    """Read a file from a sandboxed working directory.

    `work_dir` defaults to the process's CWD at construction time.
    `max_bytes` defaults to 1 MiB.
    """

    name: ClassVar[str] = "file_read"
    description: ClassVar[str] = (
        "Read a UTF-8 text file from the sandbox. Returns the file's "
        "contents as a string. Path must be relative and stay inside "
        "the configured working directory."
    )
    input_schema: ClassVar[type[BaseModel]] = _FileReadInput
    capabilities: ClassVar[frozenset[str]] = frozenset({"filesystem"})

    def __init__(
        self,
        *,
        work_dir: str | Path | None = None,
        max_bytes: int = _DEFAULT_MAX_BYTES,
    ) -> None:
        if max_bytes < 1:
            msg = f"max_bytes must be >= 1, got {max_bytes}"
            raise ValueError(msg)
        # Resolve work_dir to an absolute, real path (follows symlinks)
        # so containment checks compare apples to apples.
        self._work_dir = Path(work_dir if work_dir is not None else Path.cwd()).resolve()
        if not self._work_dir.is_dir():
            msg = f"work_dir {self._work_dir!r} is not a directory"
            raise ValueError(msg)
        self._max_bytes = max_bytes

    async def run(self, **kwargs: Any) -> str:
        path_str = kwargs["path"]
        # Reject explicitly absolute paths up front for a clearer
        # error than the contained-path check would give.
        if Path(path_str).is_absolute():
            msg = f"file_read: absolute paths are not allowed (got {path_str!r})"
            raise ValueError(msg)

        candidate = (self._work_dir / path_str).resolve()
        try:
            candidate.relative_to(self._work_dir)
        except ValueError as exc:
            msg = (
                f"file_read: path {path_str!r} resolves to {candidate!r}, "
                f"which is outside the sandbox {self._work_dir!r}"
            )
            raise ValueError(msg) from exc

        if not candidate.is_file():
            msg = f"file_read: {path_str!r} is not a file"
            raise ValueError(msg)

        size = candidate.stat().st_size
        if size > self._max_bytes:
            msg = f"file_read: {path_str!r} is {size} bytes; max_bytes={self._max_bytes}"
            raise ValueError(msg)

        text: str = candidate.read_text(encoding="utf-8")
        return text


# Default instance — sandboxed to CWD at import time, 1 MiB cap.
file_read = FileReadTool()


__all__ = ["FileReadTool", "file_read"]
