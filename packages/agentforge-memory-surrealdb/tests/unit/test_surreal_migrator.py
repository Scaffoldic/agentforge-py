"""Unit tests for `SurrealMigrator` (feat-024)."""

from __future__ import annotations

import pytest
from agentforge_core import MigrationChecksumError
from agentforge_memory_surrealdb._migrator import SurrealMigrator


@pytest.mark.asyncio
async def test_apply_pending_walks_bundled_migrations(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    migrator = SurrealMigrator(surreal_fake_runner)
    applied = await migrator.apply_pending()
    ids = [m.id for m in applied]
    assert ids[0] == "0000"
    assert ids == sorted(ids)
    again = await migrator.apply_pending()
    assert again == []


@pytest.mark.asyncio
async def test_status_returns_per_migration_state(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    migrator = SurrealMigrator(surreal_fake_runner)
    pre = await migrator.status()
    assert all(not s.applied for s in pre)
    await migrator.apply_pending()
    post = await migrator.status()
    assert all(s.applied for s in post)
    assert all(s.checksum_match for s in post)


@pytest.mark.asyncio
async def test_checksum_drift_raises(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    migrator = SurrealMigrator(surreal_fake_runner)
    await migrator.apply_pending()
    record = surreal_fake_runner.applied_migrations["0000"]
    record["checksum"] = "deadbeef" * 8
    with pytest.raises(MigrationChecksumError, match="checksum drift"):
        await migrator.apply_pending()


@pytest.mark.asyncio
async def test_apply_pending_renders_dimension_placeholder(surreal_fake_runner) -> None:  # type: ignore[no-untyped-def]
    """feat-024 v0.3 follow-up: with `variables={"dimensions": ...}`,
    the vector migration's `${dimensions}` placeholder renders at
    apply time. Checksum stays over the un-substituted template."""
    from pathlib import Path  # noqa: PLC0415

    vector_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "agentforge_memory_surrealdb"
        / "migrations"
        / "vector"
    )
    migrator = SurrealMigrator(
        surreal_fake_runner,
        variables={"dimensions": "1024"},
        migrations_path=vector_path,
    )
    await migrator.apply_pending()

    qs = [q.surrealql for q in surreal_fake_runner.queries]
    flat = " ".join(qs)
    assert "DIMENSION 1024" in flat
    assert "${dimensions}" not in flat
