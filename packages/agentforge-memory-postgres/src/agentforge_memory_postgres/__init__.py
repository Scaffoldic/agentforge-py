"""AgentForge — Postgres + pgvector memory and vector drivers.

Implements `MemoryStore` (claim audit log) and `VectorStore` (semantic
search via pgvector) over Postgres via the official `asyncpg` driver.
Sister package to `agentforge-memory-sqlite`; same locked contracts,
same conformance suites.

Per ADR-0014 every code path is async — uses `asyncpg`, never the
sync `psycopg`, in agent code paths.
"""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_memory_postgres.memory import PostgresMemoryStore
from agentforge_memory_postgres.vector import PostgresVectorStore

try:
    __version__ = _dist_version("agentforge-memory-postgres")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = ["PostgresMemoryStore", "PostgresVectorStore", "__version__"]
