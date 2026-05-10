"""Default in-process memory implementations.

`InMemoryStore` (claim audit log) and `InMemoryVectorStore` (semantic
search) ship with `agentforge` so a fresh `Agent(...)` has
durable-shaped state out of the box without external infra. Both are
safe defaults; production deployments swap to real drivers
(`agentforge-memory-sqlite`, `-postgres`) via `agentforge.yaml`.
"""

from __future__ import annotations

from agentforge.memory.in_memory import InMemoryStore
from agentforge.memory.in_memory_graph import InMemoryGraphStore
from agentforge.memory.in_memory_vector import InMemoryVectorStore

__all__ = ["InMemoryGraphStore", "InMemoryStore", "InMemoryVectorStore"]
