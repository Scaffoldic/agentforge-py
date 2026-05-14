"""Unit tests for the migration framework (feat-024)."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge_core import (
    Migration,
    MigrationChecksumError,
    discover_migrations,
)
from agentforge_core.migrations import render_migration_up
from agentforge_core.migrations.discover import _checksum
from agentforge_core.production.exceptions import ModuleError

# ---- Migration value validation ----


def test_migration_value_validates_id_format() -> None:
    body = "CREATE TABLE foo (id INT);"
    with pytest.raises(ValueError, match="4 digits"):
        Migration(id="1", name="initial", up=body, checksum=_checksum(body))


def test_migration_value_validates_id_non_digit() -> None:
    body = "CREATE TABLE foo (id INT);"
    with pytest.raises(ValueError, match="4 digits"):
        Migration(id="abcd", name="initial", up=body, checksum=_checksum(body))


def test_migration_value_validates_checksum_length() -> None:
    body = "CREATE TABLE foo (id INT);"
    with pytest.raises(ValueError, match="checksum"):
        Migration(id="0001", name="initial", up=body, checksum="too-short")


def test_migration_value_rejects_empty_name() -> None:
    body = "CREATE TABLE foo (id INT);"
    with pytest.raises(ValueError, match="name"):
        Migration(id="0001", name="", up=body, checksum=_checksum(body))


def test_migration_value_is_frozen() -> None:
    body = "CREATE TABLE foo (id INT);"
    m = Migration(id="0001", name="initial", up=body, checksum=_checksum(body))
    with pytest.raises(ValueError, match="frozen"):
        m.name = "different"  # type: ignore[misc]


# ---- Checksum stability ----


def test_checksum_is_deterministic() -> None:
    assert _checksum("hello") == _checksum("hello")


def test_checksum_normalises_line_endings() -> None:
    """CRLF and LF should produce the same checksum."""
    assert _checksum("a\r\nb") == _checksum("a\nb")
    assert _checksum("a\rb") == _checksum("a\nb")


def test_checksum_is_64_hex_chars() -> None:
    digest = _checksum("anything")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_checksum_differs_for_different_inputs() -> None:
    assert _checksum("a") != _checksum("b")


# ---- discover_migrations ----


def test_discover_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert discover_migrations(missing, suffix="sql") == []


def test_discover_returns_empty_for_empty_dir(tmp_path: Path) -> None:
    assert discover_migrations(tmp_path, suffix="sql") == []


def test_discover_returns_ordered_by_id(tmp_path: Path) -> None:
    (tmp_path / "0002_second.sql").write_text("CREATE TABLE b ();")
    (tmp_path / "0001_first.sql").write_text("CREATE TABLE a ();")
    (tmp_path / "0010_tenth.sql").write_text("CREATE TABLE c ();")
    migrations = discover_migrations(tmp_path, suffix="sql")
    ids = [m.id for m in migrations]
    assert ids == ["0001", "0002", "0010"]


def test_discover_extracts_name_from_filename(tmp_path: Path) -> None:
    (tmp_path / "0001_initial_schema.sql").write_text("CREATE TABLE a ();")
    migrations = discover_migrations(tmp_path, suffix="sql")
    assert migrations[0].name == "initial_schema"


def test_discover_filters_by_suffix(tmp_path: Path) -> None:
    (tmp_path / "0001_a.sql").write_text("SELECT 1;")
    (tmp_path / "0001_a.cypher").write_text("RETURN 1;")
    (tmp_path / "0001_a.surql").write_text("SELECT 1;")
    sql_migs = discover_migrations(tmp_path, suffix="sql")
    cypher_migs = discover_migrations(tmp_path, suffix="cypher")
    assert len(sql_migs) == 1
    assert len(cypher_migs) == 1
    assert sql_migs[0].up.startswith("SELECT")
    assert cypher_migs[0].up.startswith("RETURN")


def test_discover_ignores_files_without_id_prefix(tmp_path: Path) -> None:
    (tmp_path / "0001_valid.sql").write_text("SELECT 1;")
    (tmp_path / "README.sql").write_text("not a migration")
    (tmp_path / "notes.sql").write_text("draft")
    (tmp_path / "abc_invalid.sql").write_text("bad prefix")
    migrations = discover_migrations(tmp_path, suffix="sql")
    assert [m.id for m in migrations] == ["0001"]


def test_discover_raises_on_duplicate_id(tmp_path: Path) -> None:
    (tmp_path / "0001_first.sql").write_text("SELECT 1;")
    (tmp_path / "0001_duplicate.sql").write_text("SELECT 2;")
    with pytest.raises(ValueError, match="Duplicate migration id"):
        discover_migrations(tmp_path, suffix="sql")


def test_discover_computes_checksum_from_file_contents(tmp_path: Path) -> None:
    body = "CREATE TABLE foo (id INT);\n"
    (tmp_path / "0001_init.sql").write_text(body)
    migrations = discover_migrations(tmp_path, suffix="sql")
    assert migrations[0].checksum == _checksum(body)


# ---- render_migration_up (template) ----


def test_render_passes_through_when_variables_none() -> None:
    body = "CREATE TABLE foo (id INT);"
    assert render_migration_up(body, None) == body


def test_render_passes_through_when_variables_empty() -> None:
    body = "CREATE TABLE foo (id INT);"
    assert render_migration_up(body, {}) == body


def test_render_substitutes_named_placeholders() -> None:
    body = "CREATE TABLE vectors (embedding vector(${dimensions}));"
    rendered = render_migration_up(body, {"dimensions": "768"})
    assert "vector(768)" in rendered
    assert "${dimensions}" not in rendered


def test_render_leaves_unknown_placeholders_untouched() -> None:
    body = "CREATE TABLE vectors (col ${unknown});"
    rendered = render_migration_up(body, {"dimensions": "768"})
    # Unknown ${unknown} passes through; caller sees SQL syntax
    # error at apply time rather than a silently empty replacement.
    assert "${unknown}" in rendered


def test_render_dollar_escape_works() -> None:
    body = "SELECT '$$' AS price"
    rendered = render_migration_up(body, {"dimensions": "768"})
    assert rendered == "SELECT '$' AS price"


def test_checksum_is_over_unrendered_body() -> None:
    """Checksum must NOT vary with substitution — that's the
    whole point of the template invariant."""
    template = "CREATE TABLE vectors (embedding vector(${dimensions}));"
    checksum_template = _checksum(template)
    # The rendered body produces a *different* checksum (it
    # includes the substituted value); the framework records the
    # template's checksum, not the rendered body's, so re-deploys
    # with different `dimensions` don't trigger drift detection.
    rendered_768 = render_migration_up(template, {"dimensions": "768"})
    rendered_1536 = render_migration_up(template, {"dimensions": "1536"})
    assert _checksum(template) == checksum_template
    assert _checksum(rendered_768) != checksum_template
    assert _checksum(rendered_1536) != checksum_template


# ---- MigrationChecksumError ----


def test_checksum_error_is_module_error() -> None:
    """Subclassing ModuleError lets callers catch via existing
    error-handling patterns."""
    assert issubclass(MigrationChecksumError, ModuleError)
    err = MigrationChecksumError("checksum drift")
    assert isinstance(err, ModuleError)
