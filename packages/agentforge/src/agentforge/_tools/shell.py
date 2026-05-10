"""`shell` — sandboxed subprocess tool (feat-004).

Executes a command as a list of arguments via `asyncio.create_subprocess_exec`
(`shell=False` equivalent — no shell interpretation, no glob expansion,
no env-var interpolation). Always reads input as `list[str]`, never as
a single string, so there is no shell-injection vector.

Capabilities: `{"shell", "destructive"}` — declared up front. Future
safety guardrails (feat-018) refuse to enable destructive tools without
explicit operator opt-in.

The default instance is constructed at import time with a 30-second
timeout and CWD as the sandbox. Users wanting different limits
construct their own:

    custom = ShellTool(work_dir="/srv/jobs", timeout_s=120,
                       allowed_commands=("ls", "cat"))
    agent = Agent(tools=[custom, ...])

Sandbox enforcement:
  - `command` is a list; argv[0] is the executable.
  - `allowed_commands` (optional) restricts argv[0] to a whitelist of
    binary names. The default is `None` → no restriction (deploy with
    care).
  - `timeout_s` kills the subprocess if it runs too long.
  - Working directory pinned to `work_dir`.
  - Output truncated to `max_output_bytes` (default 64 KiB).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, ClassVar

from agentforge_core.contracts.tool import Tool
from pydantic import BaseModel, Field

_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_MAX_OUTPUT_BYTES = 64 * 1024  # 64 KiB


class _ShellInput(BaseModel):
    """Input schema for `shell`."""

    command: list[str] = Field(
        min_length=1,
        description=(
            "The command and arguments as a list, e.g. ['ls', '-la']. "
            "Strings are not interpreted by a shell — no glob expansion, "
            "no quoting, no env-var substitution. Pass each argument as "
            "a separate list element."
        ),
    )


class ShellTool(Tool):
    """Run a sandboxed subprocess via `asyncio.create_subprocess_exec`.

    `work_dir` defaults to CWD at construction time. `timeout_s`
    defaults to 30s. `allowed_commands` defaults to None (any
    command). `max_output_bytes` defaults to 64 KiB.
    """

    name: ClassVar[str] = "shell"
    description: ClassVar[str] = (
        "Run a command as a list of arguments (no shell interpretation). "
        "Returns combined stdout+stderr as a string. Capabilities: shell, "
        "destructive — deploy with caution."
    )
    input_schema: ClassVar[type[BaseModel]] = _ShellInput
    capabilities: ClassVar[frozenset[str]] = frozenset({"shell", "destructive"})

    def __init__(
        self,
        *,
        work_dir: str | Path | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        allowed_commands: tuple[str, ...] | None = None,
        max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        if timeout_s <= 0:
            msg = f"timeout_s must be > 0, got {timeout_s}"
            raise ValueError(msg)
        if max_output_bytes < 1:
            msg = f"max_output_bytes must be >= 1, got {max_output_bytes}"
            raise ValueError(msg)
        self._work_dir = Path(work_dir if work_dir is not None else Path.cwd()).resolve()
        if not self._work_dir.is_dir():
            msg = f"work_dir {self._work_dir!r} is not a directory"
            raise ValueError(msg)
        self._timeout_s = timeout_s
        self._allowed = allowed_commands
        self._max_output_bytes = max_output_bytes

    async def run(self, **kwargs: Any) -> str:
        command: list[str] = list(kwargs["command"])
        if not command:
            msg = "shell: command list is empty"
            raise ValueError(msg)
        if self._allowed is not None and command[0] not in self._allowed:
            msg = f"shell: command {command[0]!r} is not in allowed_commands ({self._allowed!r})"
            raise ValueError(msg)

        # `subprocess_exec` takes argv as separate args (not a list);
        # *command spreads it. shell=False is the default and only
        # mode for create_subprocess_exec.
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(self._work_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=self._timeout_s)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            msg = f"shell: command {command!r} exceeded timeout_s={self._timeout_s}; killed"
            raise TimeoutError(msg) from None

        if len(stdout_bytes) > self._max_output_bytes:
            stdout_bytes = stdout_bytes[: self._max_output_bytes] + b"\n... [output truncated]"
        text = stdout_bytes.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            return f"[exit {proc.returncode}]\n{text}"
        return text


# Default instance — sandboxed to CWD, 30s timeout, no whitelist.
shell = ShellTool()


__all__ = ["ShellTool", "shell"]
