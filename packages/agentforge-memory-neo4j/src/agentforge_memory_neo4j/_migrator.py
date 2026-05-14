"""`Neo4jMigrator` — Neo4j-side implementation of the feat-024
:class:`agentforge_core.Migrator` Protocol.

Migrations ship at
``agentforge_memory_neo4j/migrations/NNNN_<name>.cypher``. The
migrator splits each file on ``;`` (after stripping comments and
blank lines) and runs each statement via
:meth:`CypherRunner.execute_write` — Neo4j 5.x requires DDL
(constraints / indexes) to be one statement per transaction.
Applied migrations are tracked via ``:AgentforgeMigration`` nodes
with ``id`` / ``name`` / ``checksum`` / ``applied_at`` properties.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentforge_core.contracts.migrator import (
    Migration,
    MigrationChecksumError,
    MigrationStatus,
)
from agentforge_core.migrations import discover_migrations

from agentforge_memory_neo4j._runner import CypherRunner

_MIGRATION_LABEL = "AgentforgeMigration"


def _default_migrations_path() -> Path:
    return Path(__file__).parent / "migrations"


def _split_statements(body: str) -> list[str]:
    """Split a Cypher migration body on `;` into individual statements.

    Neo4j 5.x doesn't accept multi-statement Cypher in a single
    `run()` call (no semicolon-batching). Strip blank lines and
    single-line `//` comments before splitting; drop empty parts.
    """
    cleaned_lines: list[str] = []
    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        cleaned_lines.append(raw_line)
    cleaned = "\n".join(cleaned_lines)
    return [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]


class Neo4jMigrator:
    """Neo4j implementation of :class:`agentforge_core.Migrator`."""

    def __init__(
        self,
        runner: CypherRunner,
        *,
        migrations_path: Path | None = None,
    ) -> None:
        self._r = runner
        self._path = migrations_path or _default_migrations_path()
        self._migrations: list[Migration] = discover_migrations(self._path, suffix="cypher")

    @property
    def migrations(self) -> list[Migration]:
        return list(self._migrations)

    async def current_version(self) -> str | None:
        rows = await self._r.execute_read(
            f"MATCH (m:{_MIGRATION_LABEL}) RETURN m.id AS id ORDER BY m.id DESC LIMIT 1",
            {},
        )
        if not rows:
            return None
        return str(rows[0]["id"])

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
                    applied_at=record["applied_at"],
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
                    f"Neo4j migration {migration.id}_{migration.name} "
                    f"checksum drift: recorded {record['checksum']!r} but "
                    f"file is now {migration.checksum!r}."
                )
                raise MigrationChecksumError(msg)

        new_applied: list[Migration] = []
        for migration in self._migrations:
            if migration.id in applied:
                continue
            for stmt in _split_statements(migration.up):
                await self._r.execute_write(stmt, {})
            await self._r.execute_write(
                f"CREATE (m:{_MIGRATION_LABEL} "
                "{id: $id, name: $name, checksum: $checksum, applied_at: datetime()})",
                {
                    "id": migration.id,
                    "name": migration.name,
                    "checksum": migration.checksum,
                },
            )
            new_applied.append(migration)
        return new_applied

    async def _fetch_applied(self) -> dict[str, dict[str, Any]]:
        rows = await self._r.execute_read(
            f"MATCH (m:{_MIGRATION_LABEL}) "
            "RETURN m.id AS id, m.name AS name, m.checksum AS checksum, "
            "m.applied_at AS applied_at",
            {},
        )
        return {
            str(row["id"]): {
                "name": row["name"],
                "checksum": row["checksum"],
                "applied_at": _coerce_datetime(row.get("applied_at")),
            }
            for row in rows
        }


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_native"):  # neo4j.time.DateTime
        return value.to_native()  # type: ignore[no-any-return]
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.now(UTC)
