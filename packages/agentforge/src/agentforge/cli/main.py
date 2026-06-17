"""`agentforge` CLI entry point — argparse-based dispatcher.

No third-party CLI dep (Click, Typer) — keeps `agentforge`'s
top-level surface lean. Subcommands live in sibling modules and
are registered here.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from agentforge.cli.config_cmd import register_config_cmd
from agentforge.cli.db_cmd import register_db_cmd
from agentforge.cli.debug_cmd import register_debug_cmd
from agentforge.cli.docs_cmd import register_docs_cmd
from agentforge.cli.eval_cmd import register_eval_cmd
from agentforge.cli.health_cmd import register_health_cmd
from agentforge.cli.list_modules import register_list_modules
from agentforge.cli.module_cmd import register_module_cmd
from agentforge.cli.new_cmd import register_new_cmd
from agentforge.cli.run_cmd import register_run_cmd
from agentforge.cli.upgrade_cmd import register_upgrade_cmds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentforge",
        description="AgentForge CLI — inspect installed modules.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=_resolve_version(),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    register_list_modules(sub)
    register_config_cmd(sub)
    register_module_cmd(sub)
    register_new_cmd(sub)
    register_upgrade_cmds(sub)
    register_run_cmd(sub)
    register_eval_cmd(sub)
    register_debug_cmd(sub)
    register_db_cmd(sub)
    register_health_cmd(sub)
    register_docs_cmd(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument vector (typically `sys.argv[1:]`); pass an
            explicit list from tests.

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 1
    return int(handler(args) or 0)


def _resolve_version() -> str:
    """Return the installed `agentforge` distribution's version."""
    try:
        return version("agentforge-py")
    except PackageNotFoundError:  # pragma: no cover - unusual at runtime
        return "0.0.0+unknown"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
