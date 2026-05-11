"""`agentforge new <name>` — scaffold a new agent from a template.

feat-011 ships six templates inside `agentforge/templates/<name>/`
(see Implementation status §4.4 — local templates instead of the
spec's separate-repo design; migration to `agentforge-templates`
is a 0.4+ follow-up).

Copier handles the render; this module is the CLI wrapper +
template resolution. The lock file + marker headers are written
post-render in chunk 3.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from agentforge_core.production.exceptions import ModuleError

from agentforge.cli._scaffold_state import (
    prepend_markers,
    write_managed_files_lock,
)

_TEMPLATES = ("minimal", "code-reviewer", "patch-bot", "docs-qa", "triage", "research")
"""Templates shipped with the framework — discoverable via
`agentforge new --help`. Each lives at
`agentforge/templates/<name>/`."""


def register_new_cmd(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach `agentforge new` to the parent subparser action."""
    new = sub.add_parser(
        "new",
        help="Scaffold a new AgentForge project from a template.",
    )
    new.add_argument(
        "project_slug",
        help="Project name / directory (kebab-case, e.g. 'my-pr-reviewer').",
    )
    new.add_argument(
        "--template",
        choices=_TEMPLATES,
        default="minimal",
        help="Template to scaffold from (default: minimal).",
    )
    new.add_argument(
        "--provider",
        choices=("bedrock", "anthropic", "openai"),
        default=None,
        help="LLM provider (bedrock, anthropic, openai). Prompted when --no-prompts is not set.",
    )
    new.add_argument(
        "--no-prompts",
        action="store_true",
        help="Batch mode — use defaults for every Copier question.",
    )
    new.add_argument(
        "--dst",
        type=Path,
        default=None,
        help="Destination directory (default: ./<project_slug>).",
    )
    new.set_defaults(_handler=_run_new)


def _run_new(args: argparse.Namespace) -> int:
    """Render the chosen template into `args.dst` (or `./<slug>`)."""
    template_root = _template_root(args.template)
    if template_root is None:
        sys.stderr.write(
            f"Template {args.template!r} not shipped with this install. "
            f"Known: {', '.join(_TEMPLATES)}.\n"
        )
        return 1

    dst = args.dst if args.dst is not None else Path.cwd() / args.project_slug
    answers: dict[str, object] = {"project_slug": args.project_slug}
    if args.provider is not None:
        answers["llm_provider"] = args.provider

    try:
        _run_copier(str(template_root), str(dst), answers, defaults=args.no_prompts)
    except ModuleError as exc:
        sys.stderr.write(f"scaffolding failed: {exc}\n")
        return 1

    # feat-011 chunk 3: write the lock + prepend marker headers. Done
    # post-render so the lock reflects exactly what landed on disk.
    template_version = _template_version()
    write_managed_files_lock(
        dst,
        template_name=args.template,
        template_version=template_version,
    )
    prepend_markers(dst, template_name=args.template, template_version=template_version)

    sys.stdout.write(f"  → done. Next: cd {args.project_slug} && uv sync\n")
    return 0


def _template_version() -> str:
    """Resolve the installed `agentforge` version — used as the
    template's `source_version` in the lock file."""
    from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415

    try:
        return version("agentforge")
    except PackageNotFoundError:  # pragma: no cover
        return "0.0.0+unknown"


def _template_root(name: str) -> Path | None:
    """Resolve the template directory under `agentforge/templates/`.

    Uses `importlib.resources` so it works from the installed wheel.
    """
    from importlib import resources  # noqa: PLC0415

    try:
        root_traversable = resources.files("agentforge.templates").joinpath(name)
    except ModuleNotFoundError:
        return None
    # Materialise to a Path — Copier needs a filesystem path, not a
    # MultiplexedPath. `as_file` returns a context-managed temporary
    # path for zipped distributions; for editable installs (the
    # common case) the underlying path is real.
    with resources.as_file(root_traversable) as path:
        if not path.exists() or not (path / "copier.yml").exists():
            return None
        return Path(path)


def _run_copier(
    src: str,
    dst: str,
    data: dict[str, object],
    *,
    defaults: bool,
) -> None:
    """Run Copier's render. Wrapped so tests can mock the call."""
    from copier import run_copy  # noqa: PLC0415 — lazy to keep import cost off other CLI paths

    try:
        run_copy(
            src_path=src,
            dst_path=dst,
            data=data,
            defaults=defaults,
            unsafe=False,
            quiet=False,
        )
    except Exception as exc:
        raise ModuleError(f"copier render failed: {exc}") from exc


__all__: Sequence[str] = ["register_new_cmd"]
