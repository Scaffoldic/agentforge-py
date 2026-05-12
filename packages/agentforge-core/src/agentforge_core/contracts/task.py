"""`Task` — the locked pipeline-task ABC.

feat-015 introduces deterministic, pre-LLM analysis steps. A `Task`
emits a list of `Finding`s; `Pipeline` (in `agentforge.pipeline`)
runs a DAG of tasks in parallel and hands the consolidated findings
to the agent before the reasoning loop starts.

Subclasses declare four class attributes:

    name: ClassVar[str]
        Unique identifier within a pipeline. Must be non-empty.
    cost_estimate_usd: ClassVar[float]
        Declared cost. ``0.0`` for deterministic tasks; positive for
        tasks that call the LLM (charged against the agent's budget).
    timeout_s: ClassVar[float]
        Per-task timeout in seconds. The engine wraps each
        ``run()`` call in ``asyncio.wait_for(timeout_s)``.
    depends_on: ClassVar[tuple[str, ...]]
        Names of tasks that must finish before this one starts.
        The engine validates the DAG at construction (no cycles, no
        dangling references).

Subclasses implement ``run(context)`` and return ``list[Finding]``.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar

from agentforge_core.contracts.finding import Finding


class Task(ABC):
    """A deterministic (or LLM-using) step in a `Pipeline`."""

    name: ClassVar[str]
    cost_estimate_usd: ClassVar[float] = 0.0
    timeout_s: ClassVar[float] = 60.0
    depends_on: ClassVar[tuple[str, ...]] = ()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        if "name" not in cls.__dict__ and not _inherited_attr(cls, "name"):
            raise TypeError(
                f"{cls.__name__} must declare class attribute 'name' (see Task docstring)."
            )

    @abstractmethod
    async def run(self, context: Mapping[str, Any]) -> list[Finding]:
        """Execute the task and emit findings.

        Args:
            context: Caller-provided dict, merged with prior tasks'
                findings under the key ``"pipeline_findings_so_far"``.
                Treat as read-only; do not mutate.

        Returns:
            A list of `Finding`s. An empty list is valid.
        """


def _inherited_attr(cls: type, attr: str) -> bool:
    for base in cls.__mro__[1:]:
        if base is Task or base is object:
            continue
        if attr in base.__dict__:
            return True
    return False
