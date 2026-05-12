"""Registration helpers for shipped strategies / providers / etc.

Thin wrappers over `agentforge_core.resolver.register` that the
runtime package uses to register its built-in implementations
under canonical names. Strategy authors writing custom loops
should use `agentforge_core.resolver.register` directly; these
helpers exist so the runtime's registrations sit alongside their
class definitions for readability.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from agentforge_core.resolver import register

T = TypeVar("T", bound=type)


def register_strategy(name: str) -> Callable[[T], T]:
    """Register a class under `(strategies, name)` in the global resolver."""
    return register("strategies", name)


def register_task(name: str) -> Callable[[T], T]:
    """Register a pipeline `Task` class under `(tasks, name)` in the
    global resolver. feat-015."""
    return register("tasks", name)
