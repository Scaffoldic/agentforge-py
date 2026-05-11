"""Unit tests for `agentforge.cli.manifest_apply` (feat-010b chunk 1)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from agentforge.cli.manifest_apply import (
    apply_manifest,
    read_applied,
    reverse_manifest,
)
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.manifest import (
    EnvVarEntry,
    Manifest,
    TemplateFile,
)


def _build_manifest(**overrides) -> Manifest:
    base = {
        "category": "memory",
        "name": "postgres-test",
        "env_vars": [],
        "templates": [],
        "config_block": {},
        "next_steps": [],
    }
    base.update(overrides)
    return Manifest.model_validate(base)


# --- env vars ----------------------------------------------------


def test_apply_writes_env_var_to_new_env_example(tmp_path: Path):
    manifest = _build_manifest(
        env_vars=[
            EnvVarEntry(name="POSTGRES_DSN", description="Connection string"),
        ]
    )
    apply_manifest(manifest, distribution="agentforge-memory-postgres-test", cwd=tmp_path)
    env = (tmp_path / ".env.example").read_text()
    assert "# Connection string" in env
    assert "POSTGRES_DSN=" in env


def test_apply_env_var_is_idempotent(tmp_path: Path):
    """Re-applying with the same env var doesn't duplicate the line."""
    manifest = _build_manifest(env_vars=[EnvVarEntry(name="MY_KEY", description="x")])
    apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path)
    apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path)
    env = (tmp_path / ".env.example").read_text()
    assert env.count("MY_KEY=") == 1


def test_apply_env_var_default_value(tmp_path: Path):
    manifest = _build_manifest(
        env_vars=[EnvVarEntry(name="LOG_LEVEL", default="INFO", description="Log level")]
    )
    apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path)
    env = (tmp_path / ".env.example").read_text()
    assert "LOG_LEVEL=INFO" in env


# --- templates ---------------------------------------------------


def test_apply_copies_template_with_marker(tmp_path: Path):
    pkg = tmp_path / "_pkg"
    pkg.mkdir()
    (pkg / "init.sql").write_text("CREATE TABLE x (id INT);")

    manifest = _build_manifest(
        templates=[
            TemplateFile(source="init.sql", destination="db/migrations/0001_init.sql"),
        ]
    )
    apply_manifest(
        manifest,
        distribution="agentforge-memory-postgres-test",
        cwd=tmp_path,
        package_root=pkg,
    )
    target = tmp_path / "db" / "migrations" / "0001_init.sql"
    assert target.exists()
    body = target.read_text()
    assert "AGENTFORGE-MANAGED: agentforge-memory-postgres-test" in body
    assert "CREATE TABLE x" in body


def test_apply_template_is_idempotent_when_marker_matches(tmp_path: Path):
    pkg = tmp_path / "_pkg"
    pkg.mkdir()
    (pkg / "config.sql").write_text("SELECT 1;")

    manifest = _build_manifest(templates=[TemplateFile(source="config.sql", destination="out.sql")])
    applied_1 = apply_manifest(
        manifest, distribution="agentforge-test", cwd=tmp_path, package_root=pkg
    )
    body_1 = (tmp_path / "out.sql").read_text()

    apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path, package_root=pkg)
    body_2 = (tmp_path / "out.sql").read_text()
    assert body_1 == body_2
    assert len(applied_1.templates) == 1


def test_apply_template_refuses_overwrite_of_unmarked_file(tmp_path: Path):
    pkg = tmp_path / "_pkg"
    pkg.mkdir()
    (pkg / "src.sql").write_text("payload")
    (tmp_path / "out.sql").write_text("USER WROTE THIS")

    manifest = _build_manifest(templates=[TemplateFile(source="src.sql", destination="out.sql")])
    with pytest.raises(ModuleError, match="Refusing to overwrite"):
        apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path, package_root=pkg)


def test_apply_template_overwrite_flag_replaces_unmarked(tmp_path: Path):
    pkg = tmp_path / "_pkg"
    pkg.mkdir()
    (pkg / "src.sql").write_text("payload")
    (tmp_path / "out.sql").write_text("USER WROTE THIS")

    manifest = _build_manifest(
        templates=[TemplateFile(source="src.sql", destination="out.sql", overwrite=True)]
    )
    apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path, package_root=pkg)
    body = (tmp_path / "out.sql").read_text()
    assert "AGENTFORGE-MANAGED: agentforge-test" in body
    assert "payload" in body


def test_apply_template_missing_source_raises(tmp_path: Path):
    pkg = tmp_path / "_pkg"
    pkg.mkdir()
    manifest = _build_manifest(
        templates=[TemplateFile(source="missing.sql", destination="out.sql")]
    )
    with pytest.raises(ModuleError, match="not found in package_root"):
        apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path, package_root=pkg)


def test_apply_template_marker_extensions(tmp_path: Path):
    """Different file extensions get language-appropriate comment markers."""
    pkg = tmp_path / "_pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("print('x')")
    (pkg / "b.js").write_text("console.log('y');")
    (pkg / "c.html").write_text("<h1>z</h1>")

    manifest = _build_manifest(
        templates=[
            TemplateFile(source="a.py", destination="a.py"),
            TemplateFile(source="b.js", destination="b.js"),
            TemplateFile(source="c.html", destination="c.html"),
        ]
    )
    apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path, package_root=pkg)
    assert (tmp_path / "a.py").read_text().startswith("# AGENTFORGE-MANAGED")
    assert (tmp_path / "b.js").read_text().startswith("// AGENTFORGE-MANAGED")
    assert (tmp_path / "c.html").read_text().startswith("<!-- AGENTFORGE-MANAGED")


# --- config block ---------------------------------------------


def test_apply_merges_into_existing_agentforge_yaml(tmp_path: Path):
    (tmp_path / "agentforge.yaml").write_text("agent:\n  model: anthropic:claude-sonnet-4.7\n")
    manifest = _build_manifest(
        config_block={
            "modules": {
                "memory": {
                    "driver": "postgres",
                    "config": {"dsn": "${POSTGRES_DSN}"},
                }
            }
        }
    )
    apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path)

    with (tmp_path / "agentforge.yaml").open() as fh:
        cfg = yaml.safe_load(fh)
    assert cfg["agent"]["model"] == "anthropic:claude-sonnet-4.7"
    assert cfg["modules"]["memory"]["driver"] == "postgres"


def test_apply_creates_agentforge_yaml_when_absent(tmp_path: Path):
    manifest = _build_manifest(config_block={"agent": {"name": "from-manifest"}})
    apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path)
    cfg = yaml.safe_load((tmp_path / "agentforge.yaml").read_text())
    assert cfg["agent"]["name"] == "from-manifest"


def test_apply_rejects_list_top_level_in_existing_yaml(tmp_path: Path):
    (tmp_path / "agentforge.yaml").write_text("- not a mapping\n")
    manifest = _build_manifest(config_block={"agent": {"model": "x"}})
    with pytest.raises(ModuleError, match="must be a mapping"):
        apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path)


# --- state file ------------------------------------------------


def test_state_file_written(tmp_path: Path):
    manifest = _build_manifest(env_vars=[EnvVarEntry(name="X")])
    apply_manifest(manifest, distribution="agentforge-foo-test", cwd=tmp_path)
    state_path = tmp_path / ".agentforge-state" / "manifests" / "agentforge-foo-test.yaml"
    assert state_path.exists()
    state = yaml.safe_load(state_path.read_text())
    assert state["distribution"] == "agentforge-foo-test"
    assert [e["name"] for e in state["env_vars"]] == ["X"]


def test_read_applied_returns_none_when_absent(tmp_path: Path):
    assert read_applied(tmp_path, "agentforge-missing") is None


def test_read_applied_round_trips(tmp_path: Path):
    manifest = _build_manifest(env_vars=[EnvVarEntry(name="Y")])
    applied = apply_manifest(manifest, distribution="agentforge-foo-test", cwd=tmp_path)
    roundtripped = read_applied(tmp_path, "agentforge-foo-test")
    assert roundtripped == applied


# --- reverse ---------------------------------------------------


def test_reverse_removes_env_var(tmp_path: Path):
    manifest = _build_manifest(env_vars=[EnvVarEntry(name="DELETE_ME", description="x")])
    applied = apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path)
    assert "DELETE_ME=" in (tmp_path / ".env.example").read_text()

    reverse_manifest(applied, cwd=tmp_path, config_block=manifest.config_block)
    env = (tmp_path / ".env.example").read_text()
    assert "DELETE_ME" not in env


def test_reverse_deletes_template(tmp_path: Path):
    pkg = tmp_path / "_pkg"
    pkg.mkdir()
    (pkg / "f.sql").write_text("x")
    manifest = _build_manifest(templates=[TemplateFile(source="f.sql", destination="out.sql")])
    applied = apply_manifest(
        manifest, distribution="agentforge-test", cwd=tmp_path, package_root=pkg
    )
    assert (tmp_path / "out.sql").exists()

    reverse_manifest(applied, cwd=tmp_path, config_block=manifest.config_block)
    assert not (tmp_path / "out.sql").exists()


def test_reverse_strips_config_block(tmp_path: Path):
    (tmp_path / "agentforge.yaml").write_text("agent:\n  model: keep-me\n")
    manifest = _build_manifest(config_block={"modules": {"memory": {"driver": "postgres"}}})
    applied = apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path)
    cfg_before = yaml.safe_load((tmp_path / "agentforge.yaml").read_text())
    assert "memory" in cfg_before["modules"]

    reverse_manifest(applied, cwd=tmp_path, config_block=manifest.config_block)
    cfg_after = yaml.safe_load((tmp_path / "agentforge.yaml").read_text())
    assert cfg_after["agent"]["model"] == "keep-me"
    assert "modules" not in cfg_after  # all sub-keys removed → parent pruned


def test_reverse_deletes_state_file(tmp_path: Path):
    manifest = _build_manifest(env_vars=[EnvVarEntry(name="X")])
    applied = apply_manifest(manifest, distribution="agentforge-test", cwd=tmp_path)
    state_path = tmp_path / ".agentforge-state" / "manifests" / "agentforge-test.yaml"
    assert state_path.exists()

    reverse_manifest(applied, cwd=tmp_path, config_block=manifest.config_block)
    assert not state_path.exists()


def test_reverse_is_safe_when_files_already_gone(tmp_path: Path):
    """User deleted things manually before `remove` — don't crash."""
    pkg = tmp_path / "_pkg"
    pkg.mkdir()
    (pkg / "f.sql").write_text("x")
    manifest = _build_manifest(
        env_vars=[EnvVarEntry(name="X")],
        templates=[TemplateFile(source="f.sql", destination="out.sql")],
    )
    applied = apply_manifest(
        manifest, distribution="agentforge-test", cwd=tmp_path, package_root=pkg
    )
    # Hand-delete everything.
    (tmp_path / "out.sql").unlink()
    (tmp_path / ".env.example").unlink()

    reverse_manifest(applied, cwd=tmp_path, config_block=manifest.config_block)
    # No raise.
