"""`agentforge config {validate,show,schema}` — read-only config CLI.

All three commands invoke the loader and surface useful output:
- **validate**: loads the file, runs schema + module-schema
  validation, prints "OK" on success or the error path on failure.
- **show**: prints the fully-resolved config as YAML; `--resolved`
  expands env vars + overrides (default), `--raw` shows the parsed
  YAML pre-interpolation.
- **schema**: emits the root `AgentForgeConfig` JSON Schema for
  editor autocomplete (SchemaStore-style).

The destructive `add/swap/remove` commands ship in a follow-up
sub-feat (deferred from feat-010 alongside this PR).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import yaml
from agentforge_core.config import (
    AgentForgeConfig,
    load_config,
    validate_app_config,
    validate_module_configs,
)
from agentforge_core.production.exceptions import ModuleError
from pydantic import ValidationError


def register_config_cmd(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach the `config` subcommand + its `validate`/`show`/`schema`
    children to the parent subparser action."""
    config_parser = sub.add_parser(
        "config",
        help="Inspect and validate `agentforge.yaml`.",
    )
    config_sub = config_parser.add_subparsers(dest="config_target", required=True)

    validate = config_sub.add_parser(
        "validate",
        help="Validate `agentforge.yaml` (schema + module schemas).",
    )
    _attach_load_args(validate)
    validate.add_argument(
        "--strict-modules",
        action="store_true",
        help=(
            "Fail when a module the config references isn't installed. "
            "Default: lenient — skip missing modules and only validate "
            "the schema of installed ones."
        ),
    )
    validate.set_defaults(_handler=_run_validate)

    show = config_sub.add_parser(
        "show",
        help="Print the loaded config as YAML.",
    )
    _attach_load_args(show)
    show_mode = show.add_mutually_exclusive_group()
    show_mode.add_argument(
        "--resolved",
        action="store_true",
        help=(
            "Print after env-var interpolation + overrides (default). "
            "Shows exactly what the agent will see."
        ),
    )
    show_mode.add_argument(
        "--raw",
        action="store_true",
        help="Print the raw YAML on disk, pre-interpolation.",
    )
    show.set_defaults(_handler=_run_show)

    schema = config_sub.add_parser(
        "schema",
        help="Print the root config's JSON Schema (for IDE autocomplete).",
    )
    schema.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent level (default 2).",
    )
    schema.set_defaults(_handler=_run_schema)


def _attach_load_args(parser: argparse.ArgumentParser) -> None:
    """Args shared by `validate` and `show` — point at a file, pick
    an env layer, apply overrides."""
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Path to agentforge.yaml (default: $AGENTFORGE_CONFIG or ./agentforge.yaml).",
    )
    parser.add_argument(
        "--env",
        default=None,
        help="Environment layer (selects agentforge.<env>.yaml overlay).",
    )
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        metavar="DOTTED.PATH=VALUE",
        help="Override a config value (repeatable).",
    )


def _run_validate(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(args.path, env=args.env, overrides=args.override)
    except ModuleError as exc:
        sys.stderr.write(f"agentforge.yaml load failed: {exc}\n")
        return 1
    except ValidationError as exc:
        _print_validation_errors(exc)
        return 1
    try:
        validate_module_configs(cfg, strict=args.strict_modules)
    except ModuleError as exc:
        sys.stderr.write(f"module config validation failed: {exc}\n")
        return 1
    # Registered `app.<section>` schemas are always validated strictly
    # (feat-026 Phase 2). Unregistered / not-installed sections are
    # free-form, so `--strict-modules` governs only module resolution.
    try:
        validate_app_config(cfg)
    except ModuleError as exc:
        sys.stderr.write(f"app config validation failed: {exc}\n")
        return 1
    sys.stdout.write("OK\n")
    return 0


def _run_show(args: argparse.Namespace) -> int:
    if args.raw:
        return _show_raw(args)
    try:
        cfg = load_config(args.path, env=args.env, overrides=args.override)
    except (ModuleError, ValidationError) as exc:
        sys.stderr.write(f"agentforge.yaml load failed: {exc}\n")
        return 1
    payload = cfg.model_dump(mode="json")
    sys.stdout.write(yaml.safe_dump(payload, sort_keys=False, default_flow_style=False))
    return 0


def _show_raw(args: argparse.Namespace) -> int:
    path = args.path
    if path is None:
        env_path = os.environ.get("AGENTFORGE_CONFIG")
        path = Path(env_path) if env_path else Path.cwd() / "agentforge.yaml"
    if not Path(path).exists():
        sys.stderr.write(f"no config file at {path}\n")
        return 1
    sys.stdout.write(Path(path).read_text())
    return 0


def _run_schema(args: argparse.Namespace) -> int:
    schema = AgentForgeConfig.model_json_schema()
    sys.stdout.write(json.dumps(schema, indent=args.indent) + "\n")
    return 0


def _print_validation_errors(exc: ValidationError) -> None:
    """Render pydantic errors with their dotted YAML paths."""
    sys.stderr.write("agentforge.yaml validation failed:\n")
    for err in exc.errors(include_url=False):
        loc = ".".join(str(p) for p in err["loc"])
        sys.stderr.write(f"  {loc}: {err['msg']}\n")


__all__: Sequence[str] = ["register_config_cmd"]
