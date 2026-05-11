"""Manifest applier for `agentforge add/swap/remove module` (feat-010b).

Pure-data layer — no `pip`, no subprocess. Operates on:

- A `Manifest` (loaded from `<package>/manifest.yaml`).
- A target directory (typically `Path.cwd()`).
- An `AppliedManifest` state record (created by `apply`, consumed by
  `reverse`).

State files live at `<cwd>/.agentforge-state/manifests/<dist>.yaml`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.manifest import (
    AppliedEnvVar,
    AppliedManifest,
    AppliedTemplate,
    Manifest,
)

_STATE_DIR = Path(".agentforge-state") / "manifests"
_MARKER = "# AGENTFORGE-MANAGED:"
_ENV_EXAMPLE = ".env.example"
_DEFAULT_YAML = "agentforge.yaml"


def apply_manifest(
    manifest: Manifest,
    *,
    distribution: str,
    cwd: Path,
    config_path: Path | None = None,
    package_root: Path | None = None,
) -> AppliedManifest:
    """Apply `manifest` to the agent repo at `cwd`.

    Args:
        manifest: Loaded manifest.
        distribution: The pip distribution name (e.g.
            `agentforge-memory-postgres`) — used as the state-file
            stem and as the file marker.
        cwd: Repo root where edits land.
        config_path: Where `agentforge.yaml` lives. Defaults to
            `cwd / agentforge.yaml`.

    Returns:
        `AppliedManifest` reflecting what actually landed. Written
        to `<cwd>/.agentforge-state/manifests/<dist>.yaml` before
        return so partial failures are recoverable.

    Raises:
        ModuleError: a template's destination already exists and
            `overwrite=False`. State is written for whatever landed
            before the failure so `reverse` can clean up.
    """
    yaml_path = config_path if config_path is not None else cwd / _DEFAULT_YAML
    applied = AppliedManifest(
        distribution=distribution,
        category=manifest.category,
        name=manifest.name,
    )
    state_path = _state_path(cwd, distribution)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        for env in manifest.env_vars:
            line = _append_env_var(cwd / _ENV_EXAMPLE, env)
            if line is not None:
                applied = applied.model_copy(
                    update={
                        "env_vars": [*applied.env_vars, AppliedEnvVar(name=env.name, line=line)],
                    }
                )

        for template in manifest.templates:
            written = _copy_template(distribution, template, cwd, package_root=package_root)
            if written:
                applied = applied.model_copy(
                    update={
                        "templates": [
                            *applied.templates,
                            AppliedTemplate(destination=template.destination),
                        ],
                    }
                )

        if manifest.config_block:
            _merge_into_yaml(yaml_path, manifest.config_block)
            applied = applied.model_copy(update={"config_block_applied": True})
    finally:
        # Always persist whatever landed — partial state is better
        # than no state for `remove` to clean up against.
        _write_state(state_path, applied)
    return applied


def reverse_manifest(
    applied: AppliedManifest,
    *,
    cwd: Path,
    config_block: dict[str, Any] | None = None,
    config_path: Path | None = None,
) -> None:
    """Reverse an `AppliedManifest`: un-append env vars, delete copied
    files, un-merge the config block from `agentforge.yaml`.

    Args:
        applied: State record from a prior `apply_manifest`.
        cwd: Repo root.
        config_block: The same `Manifest.config_block` dict that was
            applied. Reversing the deep-merge requires knowing what
            keys to remove; we accept it as a parameter rather than
            re-reading the package manifest (which may already be
            uninstalled by the time `remove` runs).
        config_path: `agentforge.yaml` location. Defaults to
            `cwd / agentforge.yaml`.

    Side-effects: removes the state file on success.
    """
    yaml_path = config_path if config_path is not None else cwd / _DEFAULT_YAML

    for entry in applied.env_vars:
        _strip_env_var_line(cwd / _ENV_EXAMPLE, entry.line)
    for template in applied.templates:
        target = cwd / template.destination
        if target.exists():
            target.unlink()
    if applied.config_block_applied and config_block:
        _strip_from_yaml(yaml_path, config_block)

    state_path = _state_path(cwd, applied.distribution)
    if state_path.exists():
        state_path.unlink()


def read_applied(cwd: Path, distribution: str) -> AppliedManifest | None:
    """Load the state file for `distribution` if it exists."""
    state_path = _state_path(cwd, distribution)
    if not state_path.exists():
        return None
    with state_path.open() as fh:
        return AppliedManifest.model_validate(yaml.safe_load(fh) or {})


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _state_path(cwd: Path, distribution: str) -> Path:
    return cwd / _STATE_DIR / f"{distribution}.yaml"


def _write_state(path: Path, applied: AppliedManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        yaml.safe_dump(applied.model_dump(mode="json"), fh, sort_keys=False)


def _append_env_var(env_file: Path, entry: Any) -> str | None:
    """Append `<NAME>=<default>` to `.env.example`. Returns the line
    that was appended, or `None` if it was already present (no-op).
    """
    line = _format_env_line(entry)
    existing = env_file.read_text() if env_file.exists() else ""
    if _env_already_present(existing, entry.name):
        return None
    new = existing
    if new and not new.endswith("\n"):
        new += "\n"
    new += line + "\n"
    env_file.write_text(new)
    return line


def _format_env_line(entry: Any) -> str:
    """Format one env-var entry as a `NAME=value` line with optional
    comment."""
    value = entry.default if entry.default is not None else ""
    if entry.description:
        return f"# {entry.description}\n{entry.name}={value}"
    return f"{entry.name}={value}"


def _env_already_present(text: str, name: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{name}=") or stripped == name:
            return True
    return False


def _strip_env_var_line(env_file: Path, line: str) -> None:
    """Remove the matching env-var line (and its preceding `# ...`
    description comment) from `.env.example`."""
    if not env_file.exists():
        return
    raw = env_file.read_text()
    lines = raw.splitlines()
    # `line` may be multi-line (`# description\nNAME=value`). Split
    # on newline so we can drop each piece.
    targets = line.split("\n")
    out: list[str] = []
    skip = 0
    for current in lines:
        if skip > 0:
            skip -= 1
            continue
        if current == targets[0] and len(targets) > 1:
            window = lines[lines.index(current) : lines.index(current) + len(targets)]
            if window == targets:
                skip = len(targets) - 1
                continue
        if current in targets:
            continue
        out.append(current)
    env_file.write_text("\n".join(out) + ("\n" if raw.endswith("\n") else ""))


def _copy_template(
    distribution: str,
    template: Any,
    cwd: Path,
    *,
    package_root: Path | None = None,
) -> bool:
    """Copy `template.source` (inside the installed package) to
    `template.destination` (in `cwd`). Returns `True` if a file was
    written, `False` if the destination already exists with a matching
    marker (idempotent).

    Args:
        package_root: When provided, read templates from this directory
            instead of `importlib.resources`. Used in tests to point at
            a fake module dir.

    Raises:
        ModuleError: destination exists without the framework marker
            and `overwrite=False`.
    """
    source_text = _read_template_source(distribution, template.source, package_root)

    dest = cwd / template.destination
    marker = _marker_for(dest.suffix, distribution)
    if dest.exists():
        existing = dest.read_text(encoding="utf-8")
        if marker and marker in existing:
            return False  # idempotent — same module already wrote it
        if not template.overwrite:
            raise ModuleError(
                f"Refusing to overwrite {dest} (no framework marker; "
                f"set `overwrite: true` in the manifest if intentional)."
            )

    dest.parent.mkdir(parents=True, exist_ok=True)
    body = f"{marker}\n{source_text}" if marker else source_text
    dest.write_text(body, encoding="utf-8")
    return True


def _read_template_source(
    distribution: str,
    source: str,
    package_root: Path | None,
) -> str:
    """Read template file contents from `package_root` (tests) or via
    `importlib.resources` against the installed distribution
    (production)."""
    if package_root is not None:
        source_path = package_root / source
        if not source_path.exists():
            raise ModuleError(f"Manifest template {source!r} not found in package_root.")
        return source_path.read_text(encoding="utf-8")

    from importlib import resources  # noqa: PLC0415 — lazy import

    package_name = distribution.replace("-", "_")
    try:
        package_files = resources.files(package_name)
    except (ModuleNotFoundError, TypeError) as exc:
        raise ModuleError(
            f"Cannot locate package files for {package_name!r}: {exc}. "
            f"Was `pip install {distribution}` actually run?"
        ) from exc

    target = package_files.joinpath(source)
    try:
        return target.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ModuleError(
            f"Manifest template {source!r} not found in package {package_name}."
        ) from exc


def _marker_for(suffix: str, distribution: str) -> str | None:
    """Pick a comment-marker prefix for the given file extension."""
    if suffix in {".py", ".sh", ".yaml", ".yml", ".toml", ".ini", ".env", ".sql"}:
        return f"# AGENTFORGE-MANAGED: {distribution}"
    if suffix in {".js", ".ts", ".tsx", ".jsx", ".css"}:
        return f"// AGENTFORGE-MANAGED: {distribution}"
    if suffix in {".html", ".xml", ".md"}:
        return f"<!-- AGENTFORGE-MANAGED: {distribution} -->"
    return None


def _merge_into_yaml(path: Path, block: dict[str, Any]) -> None:
    """Deep-merge `block` into `agentforge.yaml`.

    Round-tripping plain pyyaml loses comments and reorders keys —
    documented trade-off. Users who care can edit `agentforge.yaml`
    by hand after `add`.
    """
    existing: dict[str, Any] = {}
    if path.exists():
        with path.open() as fh:
            existing = yaml.safe_load(fh) or {}
        if not isinstance(existing, dict):
            raise ModuleError(
                f"{path} must be a mapping at the top level; got {type(existing).__name__}."
            )
    merged = _deep_merge(existing, block)
    with path.open("w") as fh:
        yaml.safe_dump(merged, fh, sort_keys=False)


def _strip_from_yaml(path: Path, block: dict[str, Any]) -> None:
    """Remove keys present in `block` from `agentforge.yaml`. Conservative:
    only strips leaf values that match, then prunes empty parent dicts."""
    if not path.exists():
        return
    with path.open() as fh:
        existing = yaml.safe_load(fh) or {}
    if not isinstance(existing, dict):
        return
    pruned = _deep_strip(existing, block)
    with path.open("w") as fh:
        yaml.safe_dump(pruned, fh, sort_keys=False)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _deep_strip(base: dict[str, Any], to_remove: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in base.items():
        if key not in to_remove:
            out[key] = value
            continue
        removal = to_remove[key]
        if isinstance(value, dict) and isinstance(removal, dict):
            pruned = _deep_strip(value, removal)
            if pruned:
                out[key] = pruned
        # else: leaf matches — drop it entirely
    return out
