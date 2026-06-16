"""AgentForge — SQLite memory + vector drivers.

Implements `MemoryStore` (claim audit log) and `VectorStore` (semantic
search) over SQLite via `aiosqlite`. Zero external services required.

Per ADR-0014 every code path is async — uses `aiosqlite`, never the
blocking stdlib `sqlite3`, in agent code paths.
"""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_memory_sqlite.memory import SqliteMemoryStore
from agentforge_memory_sqlite.vector import SqliteVectorStore

try:
    __version__ = _dist_version("agentforge-memory-sqlite")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = ["SqliteMemoryStore", "SqliteVectorStore", "__version__"]
