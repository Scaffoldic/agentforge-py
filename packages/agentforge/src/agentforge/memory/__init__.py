"""Default in-process memory implementations.

`InMemoryStore` ships with `agentforge` so a fresh `Agent(...)` has
durable-shaped state out of the box without external infra. It is
the safe default; production deployments swap to a real driver
(`agentforge-memory-sqlite`, `-postgres`, etc.) via `agentforge.yaml`
once feat-005 lands.
"""

from __future__ import annotations

from agentforge.memory.in_memory import InMemoryStore

__all__ = ["InMemoryStore"]
