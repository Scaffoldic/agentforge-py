"""`Migrator` Protocol + `Migration` value type — feat-024.

A migration is a single versioned schema delta: a numbered
filename, a name, an SQL/Cypher/SurrealQL body, and a checksum
of the body. Drivers ship migrations in-package; the migrator
applies pending ones in order and records each in a per-driver
tracking table or graph node so re-runs are idempotent.

Per ADR-0007 the surface is locked at v0.1: adding a method to
:class:`Migrator` is a major version bump. The bodies of migrations
are driver-dialect-specific (SQL / Cypher / SurrealQL); the
framework only enforces filename convention, checksum stability,
ordering, and apply-once semantics.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentforge_core.production.exceptions import ModuleError

_MIGRATION_ID_RE = re.compile(r"^\d{4}$")


class Migration(BaseModel):
    """One versioned schema migration.

    The ``id`` is the 4-digit prefix of the migration filename
    (e.g. ``"0001"``); ``name`` is the snake-case description
    (e.g. ``"initial"``); ``up`` is the migration body the
    driver executes; ``checksum`` is the SHA-256 hex digest over
    the LF-normalised UTF-8 body — recorded at apply time and
    re-verified on every subsequent migrate / status invocation.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    up: str
    checksum: str = Field(min_length=64, max_length=64)

    @field_validator("id")
    @classmethod
    def _validate_id_format(cls, value: str) -> str:
        if not _MIGRATION_ID_RE.match(value):
            msg = f"Migration id must be exactly 4 digits, got {value!r}"
            raise ValueError(msg)
        return value


class MigrationStatus(BaseModel):
    """Per-migration applied-state record for :meth:`Migrator.status`.

    ``applied`` and ``applied_at`` track whether the migration has
    been recorded against this driver. ``checksum_match`` is True
    when the migration is both applied and its recorded checksum
    equals the file's current checksum — drift triggers
    :class:`MigrationChecksumError` on the next ``apply_pending``.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    migration: Migration
    applied: bool
    applied_at: datetime | None = None
    checksum_match: bool


class MigrationChecksumError(ModuleError):
    """An applied migration's recorded checksum no longer matches
    the file's checksum.

    Indicates the migration body was edited after deployment. The
    framework refuses to silently re-apply — operators must either
    restore the original file or add a forward-migration that
    expresses the intended delta.
    """


@runtime_checkable
class Migrator(Protocol):
    """Driver-specific migration runner.

    Implementations live alongside each persistent-store driver
    (`PostgresMigrator`, `SqliteMigrator`, `Neo4jMigrator`,
    `SurrealMigrator`). They share a single Protocol so the
    `agentforge db migrate` CLI can drive any of them through the
    same surface.
    """

    async def apply_pending(self) -> list[Migration]:
        """Apply every discovered migration whose id is strictly
        greater than ``await current_version()``. Returns the
        applied migrations in order.

        Raises:
            MigrationChecksumError: An already-applied migration's
                recorded checksum doesn't match the file's
                checksum. Aborts before applying any pending
                migration.
        """
        ...

    async def status(self) -> list[MigrationStatus]:
        """Return per-migration applied + checksum-match status
        for every discovered migration, sorted by id ascending.
        """
        ...

    async def current_version(self) -> str | None:
        """Return the id of the highest applied migration, or
        ``None`` if nothing has been applied yet (e.g. the
        tracking table doesn't exist).
        """
        ...
