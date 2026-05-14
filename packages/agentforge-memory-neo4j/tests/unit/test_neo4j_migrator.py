"""Unit tests for `Neo4jMigrator` (feat-024)."""

from __future__ import annotations

import pytest
from agentforge_core import MigrationChecksumError
from agentforge_memory_neo4j._migrator import Neo4jMigrator, _split_statements


def test_split_statements_strips_blank_and_comment_lines() -> None:
    body = (
        "// header comment\n"
        "CREATE CONSTRAINT foo IF NOT EXISTS\n"
        "FOR (n:Foo) REQUIRE n.id IS UNIQUE;\n"
        "\n"
        "// another comment\n"
        "CREATE INDEX bar IF NOT EXISTS\n"
        "FOR (n:Foo) ON (n.name);\n"
    )
    stmts = _split_statements(body)
    assert len(stmts) == 2
    assert all(stmt.startswith("CREATE") for stmt in stmts)


@pytest.mark.asyncio
async def test_apply_pending_walks_bundled_migrations(memory_fake_runner) -> None:  # type: ignore[no-untyped-def]
    migrator = Neo4jMigrator(memory_fake_runner)
    applied = await migrator.apply_pending()
    ids = [m.id for m in applied]
    assert ids[0] == "0000"
    assert ids == sorted(ids)
    # Re-running is a no-op.
    again = await migrator.apply_pending()
    assert again == []


@pytest.mark.asyncio
async def test_status_returns_per_migration_state(memory_fake_runner) -> None:  # type: ignore[no-untyped-def]
    migrator = Neo4jMigrator(memory_fake_runner)
    pre = await migrator.status()
    assert all(not s.applied for s in pre)
    await migrator.apply_pending()
    post = await migrator.status()
    assert all(s.applied for s in post)
    assert all(s.checksum_match for s in post)


@pytest.mark.asyncio
async def test_checksum_drift_raises(memory_fake_runner) -> None:  # type: ignore[no-untyped-def]
    migrator = Neo4jMigrator(memory_fake_runner)
    await migrator.apply_pending()
    record = memory_fake_runner._applied_migrations["0000"]
    record["checksum"] = "deadbeef" * 8
    with pytest.raises(MigrationChecksumError, match="checksum drift"):
        await migrator.apply_pending()
