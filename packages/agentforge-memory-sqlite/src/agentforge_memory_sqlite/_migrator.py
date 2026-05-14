"""`SqliteMigrator` — SQLite-side implementation of the feat-024
:class:`agentforge_core.Migrator` Protocol.

Migrations ship at
``agentforge_memory_sqlite/migrations/NNNN_<name>.sql``. The
migrator runs each pending migration via
:meth:`aiosqlite.Connection.executescript` so multi-statement files
work as written. Each migration is wrapped in an explicit
transaction so a partial failure rolls back cleanly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite
from agentforge_core.contracts.migrator import (
    Migration,
    MigrationChecksumError,
    MigrationStatus,
)
from agentforge_core.migrations import discover_migrations, render_migration_up


def _default_migrations_path() -> Path:
    return Path(__file__).parent / "migrations"


class SqliteMigrator:
    """SQLite implementation of :class:`agentforge_core.Migrator`."""

    def __init__(
        self,
        connection: aiosqlite.Connection,
        *,
        variables: dict[str, str] | None = None,
        migrations_path: Path | None = None,
    ) -> None:
        self._db = connection
        self._path = migrations_path or _default_migrations_path()
        self._variables = variables
        self._migrations: list[Migration] = discover_migrations(self._path, suffix="sql")

    @property
    def migrations(self) -> list[Migration]:
        return list(self._migrations)

    async def current_version(self) -> str | None:
        if not await self._tracking_table_exists():
            return None
        async with self._db.execute("SELECT MAX(id) AS latest FROM agentforge_migrations") as cur:
            row = await cur.fetchone()
        if row is None or row["latest"] is None:
            return None
        return str(row["latest"])

    async def status(self) -> list[MigrationStatus]:
        applied = await self._fetch_applied()
        out: list[MigrationStatus] = []
        for migration in self._migrations:
            record = applied.get(migration.id)
            if record is None:
                out.append(
                    MigrationStatus(
                        migration=migration,
                        applied=False,
                        applied_at=None,
                        checksum_match=False,
                    )
                )
                continue
            out.append(
                MigrationStatus(
                    migration=migration,
                    applied=True,
                    applied_at=_parse_iso(record["applied_at"]),
                    checksum_match=record["checksum"] == migration.checksum,
                )
            )
        return out

    async def apply_pending(self) -> list[Migration]:
        applied = await self._fetch_applied()

        for migration in self._migrations:
            record = applied.get(migration.id)
            if record is not None and record["checksum"] != migration.checksum:
                msg = (
                    f"SQLite migration {migration.id}_{migration.name} "
                    f"checksum drift: recorded {record['checksum']!r} but "
                    f"file is now {migration.checksum!r}."
                )
                raise MigrationChecksumError(msg)

        new_applied: list[Migration] = []
        for migration in self._migrations:
            if migration.id in applied:
                continue
            # `executescript` handles multi-statement migrations.
            # It implicitly commits, so we explicitly BEGIN before
            # and rely on the script's final state for the row write.
            rendered = render_migration_up(migration.up, self._variables)
            await self._db.executescript(rendered)
            await self._db.execute(
                "INSERT INTO agentforge_migrations(id, name, checksum) VALUES (?, ?, ?)",
                (migration.id, migration.name, migration.checksum),
            )
            await self._db.commit()
            new_applied.append(migration)
        return new_applied

    async def _tracking_table_exists(self) -> bool:
        async with self._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agentforge_migrations'"
        ) as cur:
            row = await cur.fetchone()
        return row is not None

    async def _fetch_applied(self) -> dict[str, dict[str, Any]]:
        if not await self._tracking_table_exists():
            return {}
        async with self._db.execute(
            "SELECT id, name, checksum, applied_at FROM agentforge_migrations"
        ) as cur:
            rows = await cur.fetchall()
        return {
            str(row["id"]): {
                "name": row["name"],
                "checksum": row["checksum"],
                "applied_at": row["applied_at"],
            }
            for row in rows
        }


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
