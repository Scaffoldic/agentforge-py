"""Unit tests for `SqliteMigrator` (feat-024)."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest
from agentforge_core import MigrationChecksumError
from agentforge_memory_sqlite._migrator import SqliteMigrator


@pytest.mark.asyncio
async def test_apply_pending_runs_bundled_migrations_in_order() -> None:
    connection = await aiosqlite.connect(":memory:")
    connection.row_factory = aiosqlite.Row
    try:
        migrator = SqliteMigrator(connection)
        applied = await migrator.apply_pending()
        ids = [m.id for m in applied]
        assert ids == sorted(ids)
        assert ids[0] == "0000"
        # Re-running is a no-op.
        again = await migrator.apply_pending()
        assert again == []
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_current_version_tracks_latest_applied() -> None:
    connection = await aiosqlite.connect(":memory:")
    connection.row_factory = aiosqlite.Row
    try:
        migrator = SqliteMigrator(connection)
        assert await migrator.current_version() is None
        applied = await migrator.apply_pending()
        expected = max(m.id for m in applied)
        assert await migrator.current_version() == expected
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_status_returns_per_migration_state() -> None:
    connection = await aiosqlite.connect(":memory:")
    connection.row_factory = aiosqlite.Row
    try:
        migrator = SqliteMigrator(connection)
        pre = await migrator.status()
        assert all(not s.applied for s in pre)

        await migrator.apply_pending()

        post = await migrator.status()
        assert all(s.applied for s in post)
        assert all(s.checksum_match for s in post)
        assert all(s.applied_at is not None for s in post)
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_checksum_drift_raises(tmp_path: Path) -> None:
    """Tamper with the recorded checksum to simulate a drifted
    migration file; apply_pending should refuse to proceed."""
    connection = await aiosqlite.connect(":memory:")
    connection.row_factory = aiosqlite.Row
    try:
        migrator = SqliteMigrator(connection)
        await migrator.apply_pending()

        # Tamper directly with the tracking table.
        await connection.execute(
            "UPDATE agentforge_migrations SET checksum = ? WHERE id = '0000'",
            ("deadbeef" * 8,),
        )
        await connection.commit()

        with pytest.raises(MigrationChecksumError, match="checksum drift"):
            await migrator.apply_pending()
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_vectors_survive_through_migrator_path(tmp_path: Path) -> None:
    """Open SqliteVectorStore via `from_path` (which now uses the
    migrator) + assert the schema works end-to-end."""
    from agentforge_core.values.vector import VectorItem  # noqa: PLC0415
    from agentforge_memory_sqlite import SqliteVectorStore  # noqa: PLC0415

    db = tmp_path / "v.db"
    async with await SqliteVectorStore.from_path(db, dimensions=4) as store:
        await store.upsert(
            [
                VectorItem(id="a", vector=(1.0, 0.0, 0.0, 0.0), text="alpha"),
            ]
        )
        results = await store.search((1.0, 0.0, 0.0, 0.0), limit=1)
        assert [m.id for m in results] == ["a"]
