"""Phoenix runner Protocol + production SDK wrapper."""

from __future__ import annotations

from typing import Any, Protocol


class PhoenixRunner(Protocol):
    """Lifecycle Protocol for Phoenix project logging."""

    def log_step(
        self,
        *,
        run_id: str,
        iteration: int,
        kind: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:  # pragma: no cover
        """Record one step in the Phoenix project."""
        ...

    def log_tool_call(
        self,
        *,
        run_id: str,
        tool_name: str,
        args_redacted: dict[str, Any],
    ) -> None:  # pragma: no cover
        """Record one tool invocation."""
        ...

    def log_run(
        self,
        *,
        run_id: str,
        attributes: dict[str, Any],
    ) -> None:  # pragma: no cover
        """Record run-level summary at finish."""
        ...

    def close(self) -> None:  # pragma: no cover
        """Release the underlying SDK client."""
        ...


class _PhoenixClientRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner wrapping ``phoenix.Client``."""

    def __init__(self, client: Any, project_name: str) -> None:
        self._client = client
        self._project_name = project_name

    def log_step(
        self,
        *,
        run_id: str,
        iteration: int,
        kind: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._client.log_event(
            project=self._project_name,
            event_name="agent.step",
            attributes={
                "run_id": run_id,
                "iteration": iteration,
                "kind": kind,
                **(metadata or {}),
            },
        )

    def log_tool_call(
        self,
        *,
        run_id: str,
        tool_name: str,
        args_redacted: dict[str, Any],
    ) -> None:
        self._client.log_event(
            project=self._project_name,
            event_name="agent.tool_call",
            attributes={
                "run_id": run_id,
                "tool": tool_name,
                "args": args_redacted,
            },
        )

    def log_run(
        self,
        *,
        run_id: str,
        attributes: dict[str, Any],
    ) -> None:
        self._client.log_event(
            project=self._project_name,
            event_name="agent.run",
            attributes={"run_id": run_id, **attributes},
        )

    def close(self) -> None:
        shutdown = getattr(self._client, "close", None)
        if callable(shutdown):
            shutdown()


__all__ = ["PhoenixRunner"]
