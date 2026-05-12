"""Pipeline-specific exceptions (feat-015)."""

from __future__ import annotations

from agentforge_core.production.exceptions import AgentForgeError


class PipelineFailure(AgentForgeError):  # noqa: N818  # locked name; parity with BudgetExceeded / GuardrailViolation
    """Raised when a `Pipeline` configured with ``on_task_error="fail"``
    encounters a task that raised.

    The first failed task's name is on ``task_name``; the original
    exception is chained via ``__cause__``.
    """

    def __init__(self, task_name: str, cause: BaseException) -> None:
        super().__init__(f"pipeline task {task_name!r} failed: {cause}")
        self.task_name = task_name
        self.__cause__ = cause
