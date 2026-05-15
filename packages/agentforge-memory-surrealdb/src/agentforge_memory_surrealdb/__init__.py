"""AgentForge — SurrealDB memory + vector + graph drivers.

SurrealDB is uniquely multi-modal — a single connection supports
documents, vectors, and graphs. This package implements all three
locked contracts (`MemoryStore`, `VectorStore`, `GraphStore`) over
the official `surrealdb` async SDK.
"""

from __future__ import annotations

from agentforge_memory_surrealdb.graph import SurrealGraphStore
from agentforge_memory_surrealdb.memory import SurrealMemoryStore
from agentforge_memory_surrealdb.vector import SurrealVectorStore

__version__ = "0.2.0"

__all__ = [
    "SurrealGraphStore",
    "SurrealMemoryStore",
    "SurrealVectorStore",
    "__version__",
]
