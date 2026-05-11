"""`agentforge list modules` — show every registered module.

Triggers the resolver's lazy entry-point discovery (feat-010 chunk
1) so the table reflects every `agentforge-*` package pip-installed
in the active environment.

Output groups by category; `--category` narrows; `--json` emits
machine-readable output for piping into other tools.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Iterable

from agentforge_core import ModuleInfo, Resolver


def register_list_modules(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach the `list` subcommand + its `modules` child."""
    list_parser = sub.add_parser(
        "list",
        help="Inspect installed AgentForge modules.",
    )
    list_sub = list_parser.add_subparsers(dest="list_target", required=True)

    modules = list_sub.add_parser(
        "modules",
        help="Show every registered module, grouped by category.",
    )
    modules.add_argument(
        "--category",
        help="Filter to one category (providers, memory, tools, ...).",
    )
    modules.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a text table.",
    )
    modules.set_defaults(_handler=_run_list_modules)


def _run_list_modules(args: argparse.Namespace) -> int:
    infos = Resolver.global_().list_installed(category=args.category)
    if args.json:
        sys.stdout.write(_format_json(infos) + "\n")
        return 0
    sys.stdout.write(_format_table(infos))
    return 0


def _format_json(infos: Iterable[ModuleInfo]) -> str:
    return json.dumps([m.model_dump(mode="json") for m in infos], indent=2)


def _format_table(infos: Iterable[ModuleInfo]) -> str:
    """Render a grouped-by-category text table.

    Empty registry prints a friendly hint instead of nothing.
    """
    grouped: dict[str, list[ModuleInfo]] = defaultdict(list)
    for info in infos:
        grouped[info.category].append(info)

    if not grouped:
        return (
            "No modules registered.\n"
            "Install one with `uv add agentforge-bedrock` (or any agentforge-* package),\n"
            "or register a custom class with `@register('category', 'name')`.\n"
        )

    lines: list[str] = []
    for category in sorted(grouped):
        lines.append(f"\n{category.upper()}")
        for info in grouped[category]:
            origin = (
                f"  ({info.package} {info.version})"
                if info.package and info.version
                else "  (in-process)"
            )
            lines.append(f"  {info.name:<28}{origin}")
    return "\n".join(lines) + "\n"
