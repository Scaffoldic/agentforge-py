"""AgentForge — Postgres + pgvector memory and vector drivers.

Implements `MemoryStore` (claim audit log) and `VectorStore` (semantic
search via pgvector) over Postgres via the official `asyncpg` driver.
Sister package to `agentforge-memory-sqlite`; same locked contracts,
same conformance suites.

Per ADR-0014 every code path is async — uses `asyncpg`, never the
sync `psycopg`, in agent code paths.
"""

from __future__ import annotations

from agentforge_memory_postgres.memory import PostgresMemoryStore
from agentforge_memory_postgres.vector import PostgresVectorStore

__version__ = "0.2.1"

__all__ = ["PostgresMemoryStore", "PostgresVectorStore", "__version__"]
