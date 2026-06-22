"""AgentForge — Kùzu embedded graph driver (feat-027).

Implements `GraphStore` over an embedded, file-backed Kùzu database: a
persistent property graph in a single directory, no server, no network —
the graph analogue of the SQLite `MemoryStore`.

Per ADR-0014 the public surface is async; Kùzu's Python driver is
synchronous, so blocking calls are dispatched via `asyncio.to_thread`.
"""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_memory_kuzu.graph import KuzuGraphStore

try:
    __version__ = _dist_version("agentforge-memory-kuzu")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = [
    "KuzuGraphStore",
    "__version__",
]
