"""YAML loader with env-var interpolation for `agentforge.yaml`.

Per ADR-0013, configuration is *data*: the loader supports env-var
interpolation (`${VAR}`, `${VAR:default}`, `${VAR:?error}`, `$$` →
`$`) and Pydantic validation, but no Jinja, no dynamic imports, no
arbitrary template logic.

Resolution order (last wins):
    1. Defaults from each Pydantic model.
    2. agentforge.yaml on disk (if present).
    3. Constructor kwargs to Agent (handled in `agentforge.agent`).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from agentforge_core.production.exceptions import ModuleError

from agentforge.config.schema import AgentForgeConfig

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
    """Interpolate env-var references inside a string."""

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


def load_config(path: Path | str | None = None) -> AgentForgeConfig:
    """Load and validate `agentforge.yaml`.

    Args:
        path: Path to the YAML file. If None, looks for
            `./agentforge.yaml` in the current working directory; if
            absent, returns the default config.

    Returns:
        Validated `AgentForgeConfig`.

    Raises:
        ModuleError: env-var interpolation or YAML parse error.
        ValidationError: schema validation failed.
    """
    if path is None:
        candidate = Path.cwd() / "agentforge.yaml"
        if not candidate.exists():
            return AgentForgeConfig()
        path = candidate
    path = Path(path)
    with path.open() as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ModuleError(
            f"agentforge.yaml at {path} must be a mapping at the top level; "
            f"got {type(raw).__name__}."
        )
    interpolated = _walk(raw)
    return AgentForgeConfig.model_validate(interpolated)
