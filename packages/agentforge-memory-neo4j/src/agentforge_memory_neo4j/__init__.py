"""AgentForge — Neo4j memory + graph drivers.

Implements `MemoryStore` (claim audit log) and `GraphStore` (knowledge
graph traversal) over Neo4j via the official `neo4j` async driver.

Per ADR-0014 every code path is async — uses `neo4j.AsyncGraphDatabase`,
not the sync driver.
"""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_memory_neo4j.graph import Neo4jGraphStore
from agentforge_memory_neo4j.memory import Neo4jMemoryStore
from agentforge_memory_neo4j.vector import Neo4jVectorStore

try:
    __version__ = _dist_version("agentforge-memory-neo4j")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = [
    "Neo4jGraphStore",
    "Neo4jMemoryStore",
    "Neo4jVectorStore",
    "__version__",
]
