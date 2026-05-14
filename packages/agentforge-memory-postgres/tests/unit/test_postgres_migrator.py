"""Unit tests for `PostgresMigrator` against the fake asyncpg runner
(feat-024)."""

from __future__ import annotations

import pytest
from agentforge_core import MigrationChecksumError
from agentforge_memory_postgres._migrator import PostgresMigrator


@pytest.mark.asyncio
async def test_apply_pending_applies_all_bundled_migrations(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """Empty store → `apply_pending` walks every bundled migration
    in id order and records each row in the tracking table."""
    migrator = PostgresMigrator(postgres_fake_runner)
    applied = await migrator.apply_pending()
    ids = [m.id for m in applied]
    # Bundled package ships at least 0000 (tracking) + 0001 (initial).
    assert ids[0] == "0000"
    assert "0001" in ids
    # Re-running is a no-op.
    again = await migrator.apply_pending()
    assert again == []


@pytest.mark.asyncio
async def test_current_version_tracks_latest_applied(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    migrator = PostgresMigrator(postgres_fake_runner)
    assert await migrator.current_version() is None
    applied = await migrator.apply_pending()
    expected_latest = max(m.id for m in applied)
    assert await migrator.current_version() == expected_latest


@pytest.mark.asyncio
async def test_status_returns_per_migration_state(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    migrator = PostgresMigrator(postgres_fake_runner)
    # All pending before apply.
    pre = await migrator.status()
    assert all(not s.applied for s in pre)
    assert all(not s.checksum_match for s in pre)

    await migrator.apply_pending()

    post = await migrator.status()
    assert all(s.applied for s in post)
    assert all(s.checksum_match for s in post)
    assert all(s.applied_at is not None for s in post)


@pytest.mark.asyncio
async def test_checksum_drift_raises(postgres_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """Recording a different checksum (simulating an edited migration
    file) triggers `MigrationChecksumError` on the next call."""
    migrator = PostgresMigrator(postgres_fake_runner)
    await migrator.apply_pending()

    # Tamper with the recorded checksum for migration 0000.
    record = postgres_fake_runner.applied_migrations["0000"]
    record["checksum"] = "deadbeef" * 8  # 64 hex chars but wrong

    with pytest.raises(MigrationChecksumError, match="checksum drift"):
        await migrator.apply_pending()
