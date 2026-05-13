"""In-memory `PhoenixRunner` for unit tests + downstream integration."""

from __future__ import annotations

from typing import Any


class FakePhoenixRunner:
    """In-memory recorder of every Phoenix call."""

    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.closed = False

    def log_step(
        self,
        *,
        run_id: str,
        iteration: int,
        kind: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.steps.append(
            {
                "run_id": run_id,
                "iteration": iteration,
                "kind": kind,
                "metadata": dict(metadata or {}),
            }
        )

    def log_tool_call(
        self,
        *,
        run_id: str,
        tool_name: str,
        args_redacted: dict[str, Any],
    ) -> None:
        self.tool_calls.append(
            {
                "run_id": run_id,
                "tool": tool_name,
                "args": dict(args_redacted),
            }
        )

    def log_run(
        self,
        *,
        run_id: str,
        attributes: dict[str, Any],
    ) -> None:
        self.runs.append({"run_id": run_id, "attributes": dict(attributes)})

    def close(self) -> None:
        self.closed = True


__all__ = ["FakePhoenixRunner"]
