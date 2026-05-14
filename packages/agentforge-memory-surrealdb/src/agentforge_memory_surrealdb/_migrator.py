"""`SurrealMigrator` — SurrealDB-side implementation of the feat-024
:class:`agentforge_core.Migrator` Protocol.

Migrations ship at
``agentforge_memory_surrealdb/migrations/NNNN_<name>.surql``. The
migrator submits each migration body as a single
:meth:`SurrealRunner.query` call — SurrealDB v1.x doesn't expose
multi-statement transactions, so a partial failure mid-migration
leaves the DB in a half-applied state. Operators should single-flight
the migrate call in production deployments.

Applied migrations are tracked in the ``agentforge_migrations``
SurrealDB table.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agentforge_core.contracts.migrator import (
    Migration,
    MigrationChecksumError,
    MigrationStatus,
)
from agentforge_core.migrations import discover_migrations, render_migration_up

from agentforge_memory_surrealdb._runner import SurrealRunner

_MIGRATIONS_TABLE = "agentforge_migrations"


def _default_migrations_path() -> Path:
    return Path(__file__).parent / "migrations"


def _normalise_query_result(result: Any) -> list[dict[str, Any]]:
    """SurrealDB SELECT results may be wrapped in a single-element
    list (`[[{...}, ...]]`); flatten the outer layer."""
    if not result:
        return []
    if isinstance(result, list) and result and isinstance(result[0], list):
        return list(result[0])
    if isinstance(result, list):
        return list(result)
    return []


class SurrealMigrator:
    """SurrealDB implementation of :class:`agentforge_core.Migrator`."""

    def __init__(
        self,
        runner: SurrealRunner,
        *,
        variables: dict[str, str] | None = None,
        migrations_path: Path | None = None,
    ) -> None:
        self._r = runner
        self._path = migrations_path or _default_migrations_path()
        self._variables = variables
        self._migrations: list[Migration] = discover_migrations(self._path, suffix="surql")

    @property
    def migrations(self) -> list[Migration]:
        return list(self._migrations)

    async def current_version(self) -> str | None:
        rows = await self._fetch_applied()
        if not rows:
            return None
        return max(rows)

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
                    applied_at=_coerce_datetime(record.get("applied_at")),
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
                    f"SurrealDB migration {migration.id}_{migration.name} "
                    f"checksum drift: recorded {record['checksum']!r} but "
                    f"file is now {migration.checksum!r}."
                )
                raise MigrationChecksumError(msg)

        new_applied: list[Migration] = []
        for migration in self._migrations:
            if migration.id in applied:
                continue
            rendered = render_migration_up(migration.up, self._variables)
            await self._r.query(rendered)
            await self._r.query(
                f"CREATE type::thing('{_MIGRATIONS_TABLE}', $id) "  # nosec B608
                "CONTENT { af_id: $id, name: $name, checksum: $checksum, "
                "applied_at: time::now() }",
                {
                    "id": migration.id,
                    "name": migration.name,
                    "checksum": migration.checksum,
                },
            )
            new_applied.append(migration)
        return new_applied

    async def _fetch_applied(self) -> dict[str, dict[str, Any]]:
        try:
            result = await self._r.query(
                f"SELECT * FROM {_MIGRATIONS_TABLE}"  # noqa: S608  # nosec B608
            )
        except Exception:
            # Tracking table doesn't exist yet — first run.
            return {}
        rows = _normalise_query_result(result)
        return {str(row["af_id"]): row for row in rows if "af_id" in row}


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
