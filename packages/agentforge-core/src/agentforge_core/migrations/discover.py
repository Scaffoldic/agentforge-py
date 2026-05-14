"""Filesystem migration discovery (feat-024).

Drivers store migration files at
``<package>/migrations/NNNN_<snake_name>.<ext>`` where ``<ext>`` is
the driver's dialect (``sql`` / ``cypher`` / ``surql``). This
module loads every matching file from a directory, hashes its
contents, and returns a list of :class:`Migration` values sorted by
id ascending.

Filename convention is strict: the 4-digit prefix must be followed
by an underscore and a snake-case name (``[a-z0-9_]+``). Files that
don't match are silently ignored — operators can drop drafts and
notes alongside without breaking the discovery.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from agentforge_core.contracts.migrator import Migration

_FILENAME_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)$")


def _checksum(text: str) -> str:
    """SHA-256 hex digest over ``text`` after LF normalisation."""
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def discover_migrations(path: Path, *, suffix: str) -> list[Migration]:
    """Load every ``NNNN_<name>.<suffix>`` file in ``path``.

    Args:
        path: Directory to scan. Non-existent or non-directory paths
            return an empty list (so a driver without bundled
            migrations is a no-op rather than an error).
        suffix: File extension without the dot — e.g. ``"sql"`` for
            Postgres, ``"cypher"`` for Neo4j.

    Returns:
        Migrations sorted by id ascending. Duplicate ids raise
        :class:`ValueError`.
    """
    if not path.exists() or not path.is_dir():
        return []

    pattern = f"*.{suffix}"
    seen_ids: set[str] = set()
    migrations: list[Migration] = []
    for file_path in sorted(path.glob(pattern)):
        stem = file_path.stem
        match = _FILENAME_RE.match(stem)
        if match is None:
            continue
        migration_id, name = match.group(1), match.group(2)
        if migration_id in seen_ids:
            msg = (
                f"Duplicate migration id {migration_id!r} in {path}; "
                f"found at {file_path.name!r} but already seen."
            )
            raise ValueError(msg)
        seen_ids.add(migration_id)
        body = file_path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                id=migration_id,
                name=name,
                up=body,
                checksum=_checksum(body),
            )
        )

    migrations.sort(key=lambda m: m.id)
    return migrations
