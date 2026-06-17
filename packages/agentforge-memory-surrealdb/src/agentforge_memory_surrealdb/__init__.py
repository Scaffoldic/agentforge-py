"""AgentForge — SurrealDB memory + vector + graph drivers.

SurrealDB is uniquely multi-modal — a single connection supports
documents, vectors, and graphs. This package implements all three
locked contracts (`MemoryStore`, `VectorStore`, `GraphStore`) over
the official `surrealdb` async SDK.
"""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_memory_surrealdb.graph import SurrealGraphStore
from agentforge_memory_surrealdb.memory import SurrealMemoryStore
from agentforge_memory_surrealdb.vector import SurrealVectorStore

try:
    __version__ = _dist_version("agentforge-memory-surrealdb")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = [
    "SurrealGraphStore",
    "SurrealMemoryStore",
    "SurrealVectorStore",
    "__version__",
]
