"""Migration discovery + checksum helpers (feat-024).

Drivers consume :func:`discover_migrations` to load their bundled
migration files at startup. The contract type :class:`Migration`
+ :class:`Migrator` Protocol live in
:mod:`agentforge_core.contracts.migrator`.
"""

from __future__ import annotations

from agentforge_core.migrations.discover import _checksum, discover_migrations

__all__ = ["_checksum", "discover_migrations"]
