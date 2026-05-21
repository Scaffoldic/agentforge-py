"""AgentForge — SQLite memory + vector drivers.

Implements `MemoryStore` (claim audit log) and `VectorStore` (semantic
search) over SQLite via `aiosqlite`. Zero external services required.

Per ADR-0014 every code path is async — uses `aiosqlite`, never the
blocking stdlib `sqlite3`, in agent code paths.
"""

from __future__ import annotations

from agentforge_memory_sqlite.memory import SqliteMemoryStore
from agentforge_memory_sqlite.vector import SqliteVectorStore

__version__ = "0.2.3"

__all__ = ["SqliteMemoryStore", "SqliteVectorStore", "__version__"]
