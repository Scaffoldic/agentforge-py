"""YAML loader for `agentforge.yaml` (feat-012).

Resolution order (last wins) per spec §4.3:

    1. Defaults from each Pydantic model.
    2. agentforge.yaml on disk (if present).
    3. agentforge.<env>.yaml (if AGENTFORGE_ENV set).
    4. Env-var interpolation inside YAML values.
    5. CLI / loader-API `--override agent.budget.usd=10` arguments.
    6. Constructor kwargs to Agent (handled in `agentforge.agent`).

Env-var interpolation syntax (feat-001):
- `${VAR}` — required; raises at load if missing.
- `${VAR:default}` — optional with default.
- `${VAR:?error message}` — required with custom error.
- `$$` — literal `$`.

Env-var shortcuts honoured by `load_config`:
- `AGENTFORGE_CONFIG` — overrides the default `./agentforge.yaml`
  path (lowest precedence — still beaten by an explicit `path=`).
- `AGENTFORGE_ENV` — picks the overlay file (e.g. `production` →
  `agentforge.production.yaml` next to the base file).
- `AGENTFORGE_LOG_LEVEL` — applied after schema validation to
  `cfg.logging.level`.

Per ADR-0013, the loader is data only — no Jinja, no dynamic
imports, no template logic. Behaviour goes in Python code.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from agentforge_core.config.schema import AgentForgeConfig
from agentforge_core.production.exceptions import ModuleError

_INTERP_RE = re.compile(
    r"""
    \$\$                     # $$ -> literal $
    | \$\{                   # ${
        (?P<name>[A-Z_][A-Z0-9_]*)
        (?:
            :
            (?:
                \?(?P<error>[^}]*)
                | (?P<default>[^}]*)
            )
        )?
      \}
    """,
    re.VERBOSE,
)


def _interp(value: str) -> str:
    """Interpolate env-var references inside a single string."""

    def repl(match: re.Match[str]) -> str:
        if match.group(0) == "$$":
            return "$"
        name = match.group("name")
        error = match.group("error")
        default = match.group("default")
        env_value = os.environ.get(name)
        if env_value is not None:
            return env_value
        if error is not None:
            raise ModuleError(f"Required env var {name} not set: {error}")
        if default is not None:
            return default
        raise ModuleError(f"Required env var {name} not set (no default provided).")

    return _INTERP_RE.sub(repl, value)


def _walk(value: Any) -> Any:
    """Recursively interpolate strings inside a config tree."""
    if isinstance(value, str):
        return _interp(value)
    if isinstance(value, dict):
        return {k: _walk(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v) for v in value]
    return value


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursive dict merge — overlay wins; lists replace wholesale.

    Per spec §4.3 the overlay file's lists replace, not append. This
    keeps the YAML behaviour predictable; users who want to extend
    a list write the full list in the overlay.
    """
    out: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def parse_overrides(overrides: list[str]) -> dict[str, Any]:
    """Parse `["agent.budget.usd=10", ...]` into a nested dict.

    Each entry is `<dotted.path>=<value>`. Values are YAML-parsed via
    `yaml.safe_load` so numbers, booleans, and inline lists / dicts
    work without surprise (`agent.tools=[a, b]` -> `["a", "b"]`).

    Raises:
        ModuleError: malformed override (missing `=`, empty path, etc.)
    """
    out: dict[str, Any] = {}
    for entry in overrides:
        if "=" not in entry:
            raise ModuleError(f"Invalid override {entry!r}: expected '<path>=<value>'.")
        path, _, raw_value = entry.partition("=")
        path = path.strip()
        if not path:
            raise ModuleError(f"Invalid override {entry!r}: empty path before '='.")
        parts = path.split(".")
        if any(not p for p in parts):
            raise ModuleError(f"Invalid override {entry!r}: empty path segment.")
        try:
            value = yaml.safe_load(raw_value)
        except yaml.YAMLError as exc:
            raise ModuleError(
                f"Invalid override {entry!r}: value not parseable as YAML ({exc})."
            ) from exc
        # Walk down `out`, creating dicts as needed; assign at the leaf.
        cursor = out
        for part in parts[:-1]:
            existing = cursor.get(part)
            if not isinstance(existing, dict):
                cursor[part] = {}
            cursor = cursor[part]
        cursor[parts[-1]] = value
    return out


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file; require a mapping at the top level."""
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ModuleError(
            f"agentforge.yaml at {path} must be a mapping at the top level; "
            f"got {type(raw).__name__}."
        )
    return raw


def _env_overlay_path(base: Path, env: str) -> Path:
    """Compute the overlay path next to `base`: foo.yaml → foo.<env>.yaml."""
    return base.with_suffix(f".{env}{base.suffix}")


def load_config(
    path: Path | str | None = None,
    *,
    env: str | None = None,
    overrides: list[str] | None = None,
) -> AgentForgeConfig:
    """Load + validate `agentforge.yaml` with full feat-012 resolution.

    Args:
        path: Explicit path to the YAML file. If `None`, falls back to
            `AGENTFORGE_CONFIG` env var, then `./agentforge.yaml`. If
            no file exists at any of these, returns the default config.
        env: Environment name. Selects the overlay file
            `agentforge.<env>.yaml` next to the base. If `None`, falls
            back to `AGENTFORGE_ENV`.
        overrides: List of `"<dotted.path>=<value>"` strings to apply
            after env-var interpolation and before schema validation.

    Returns:
        Validated `AgentForgeConfig` with `AGENTFORGE_LOG_LEVEL`
        applied to `cfg.logging.level` post-validation if set.

    Raises:
        ModuleError: env-var interpolation, layered-file, or override
            problem.
        pydantic.ValidationError: schema validation failed.
    """
    resolved_path = _resolve_path(path)
    if resolved_path is None or not resolved_path.exists():
        merged: dict[str, Any] = {}
    else:
        merged = _read_yaml(resolved_path)
        # Layered env file overlays the base. Missing overlay is fine
        # (env-without-file is just "use base").
        resolved_env = env if env is not None else os.environ.get("AGENTFORGE_ENV")
        if resolved_env:
            overlay_path = _env_overlay_path(resolved_path, resolved_env)
            if overlay_path.exists():
                merged = _deep_merge(merged, _read_yaml(overlay_path))

    interpolated = _walk(merged)
    if overrides:
        interpolated = _deep_merge(interpolated, parse_overrides(overrides))

    config = AgentForgeConfig.model_validate(interpolated)
    return _apply_env_log_level(config)


def _resolve_path(path: Path | str | None) -> Path | None:
    """Resolve the config-file path with `AGENTFORGE_CONFIG` fallback.

    Order of precedence:
    1. Explicit `path` argument.
    2. `AGENTFORGE_CONFIG` env var.
    3. `./agentforge.yaml` (default).
    """
    if path is not None:
        return Path(path)
    env_path = os.environ.get("AGENTFORGE_CONFIG")
    if env_path:
        return Path(env_path)
    candidate = Path.cwd() / "agentforge.yaml"
    return candidate if candidate.exists() else None


def _apply_env_log_level(config: AgentForgeConfig) -> AgentForgeConfig:
    """Apply `AGENTFORGE_LOG_LEVEL` over the validated config.

    This is a post-validation override so users can flip log level
    without touching the file (debugging, CI). Implemented via
    `model_copy` to keep the model frozen-friendly.
    """
    level = os.environ.get("AGENTFORGE_LOG_LEVEL")
    if not level:
        return config
    new_logging = config.logging.model_copy(update={"level": level})
    return config.model_copy(update={"logging": new_logging})
