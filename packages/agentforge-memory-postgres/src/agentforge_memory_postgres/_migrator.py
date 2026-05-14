"""`PostgresMigrator` — Postgres-side implementation of the feat-024
:class:`agentforge_core.Migrator` Protocol.

Migrations ship at
``agentforge_memory_postgres/migrations/NNNN_<name>.sql``. The first
migration (``0000_migrations_table.sql``) creates the
``agentforge_migrations`` tracking table; subsequent migrations carry
the actual schema deltas. Each migration is executed inside its own
asyncpg transaction so a partial failure rolls back cleanly.

The migrator consumes the existing :class:`PostgresRunner` Protocol
so unit tests can inject the same fake the rest of the package uses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentforge_core.contracts.migrator import (
    Migration,
    MigrationChecksumError,
    MigrationStatus,
)
from agentforge_core.migrations import discover_migrations, render_migration_up

from agentforge_memory_postgres._runner import PostgresRunner

_MIGRATIONS_TABLE = "agentforge_migrations"

_SELECT_APPLIED_SQL = (
    f"SELECT id, name, checksum, applied_at "  # noqa: S608  # nosec B608
    f"  FROM {_MIGRATIONS_TABLE} ORDER BY id"
)
_INSERT_APPLIED_SQL = (
    f"INSERT INTO {_MIGRATIONS_TABLE} (id, name, checksum) "  # noqa: S608  # nosec B608
    f"VALUES ($1, $2, $3)"
)
_TABLE_EXISTS_SQL = "SELECT to_regclass($1) IS NOT NULL AS exists_"  # type checker hint


def _default_migrations_path() -> Path:
    """Return the in-package migrations directory."""
    return Path(__file__).parent / "migrations"


class PostgresMigrator:
    """Postgres implementation of :class:`agentforge_core.Migrator`.

    Args:
        runner: Live `PostgresRunner` (production or fake) — the
            same one the rest of the driver uses.
        migrations_path: Override for the in-package migrations
            directory (test fixtures use this).
    """

    def __init__(
        self,
        runner: PostgresRunner,
        *,
        variables: dict[str, str] | None = None,
        migrations_path: Path | None = None,
    ) -> None:
        self._r = runner
        self._path = migrations_path or _default_migrations_path()
        self._variables = variables
        self._migrations: list[Migration] = discover_migrations(self._path, suffix="sql")

    @property
    def migrations(self) -> list[Migration]:
        return list(self._migrations)

    async def current_version(self) -> str | None:
        if not await self._tracking_table_exists():
            return None
        rows = await self._r.fetch(_SELECT_APPLIED_SQL)
        if not rows:
            return None
        return str(max(row["id"] for row in rows))

    async def status(self) -> list[MigrationStatus]:
        applied = await self._fetch_applied()
        results: list[MigrationStatus] = []
        for migration in self._migrations:
            record = applied.get(migration.id)
            if record is None:
                results.append(
                    MigrationStatus(
                        migration=migration,
                        applied=False,
                        applied_at=None,
                        checksum_match=False,
                    )
                )
                continue
            results.append(
                MigrationStatus(
                    migration=migration,
                    applied=True,
                    applied_at=record["applied_at"],
                    checksum_match=record["checksum"] == migration.checksum,
                )
            )
        return results

    async def apply_pending(self) -> list[Migration]:
        applied = await self._fetch_applied()

        # Verify previously-applied migrations' checksums haven't drifted
        # before applying anything new.
        for migration in self._migrations:
            record = applied.get(migration.id)
            if record is not None and record["checksum"] != migration.checksum:
                msg = (
                    f"Postgres migration {migration.id}_{migration.name} "
                    f"checksum drift: recorded {record['checksum']!r} but "
                    f"file is now {migration.checksum!r}."
                )
                raise MigrationChecksumError(msg)

        new_applied: list[Migration] = []
        for migration in self._migrations:
            if migration.id in applied:
                continue
            rendered = render_migration_up(migration.up, self._variables)
            await self._r.execute(rendered)
            await self._r.execute(
                _INSERT_APPLIED_SQL,
                migration.id,
                migration.name,
                migration.checksum,
            )
            new_applied.append(migration)
        return new_applied

    async def _tracking_table_exists(self) -> bool:
        row = await self._r.fetchrow(_TABLE_EXISTS_SQL, _MIGRATIONS_TABLE)
        if row is None:
            return False
        return bool(row["exists_"])

    async def _fetch_applied(self) -> dict[str, dict[str, Any]]:
        if not await self._tracking_table_exists():
            return {}
        rows = await self._r.fetch(_SELECT_APPLIED_SQL)
        return {
            str(row["id"]): {
                "name": row["name"],
                "checksum": row["checksum"],
                "applied_at": row["applied_at"],
            }
            for row in rows
        }
