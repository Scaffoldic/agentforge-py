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

import yaml
from agentforge_core.production.exceptions import ModuleError

from agentforge.cli._scaffold_state import (
    answers_path,
    prepend_markers,
    write_managed_files_lock,
)
from agentforge.cli._shared_scaffold import inject_shared_scaffold

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

    # bug-007 fix: persist the resolved scaffold answers ourselves.
    # Copier's `_answers_file` directive doesn't write reliably for
    # in-package templates; without `answers.yml`, `agentforge upgrade`
    # has nothing to re-render from. Must precede inject_shared_scaffold
    # because that step reads answers.yml for its Jinja context.
    _write_answers_file(
        dst,
        template_name=args.template,
        template_version=template_version,
        project_slug=args.project_slug,
        llm_provider=args.provider,
    )

    # feat-019: inject shared runbooks + AGENTS.md / CLAUDE.md /
    # .cursorrules / .github/copilot-instructions.md into every
    # scaffolded agent.
    shared_count = inject_shared_scaffold(
        dst,
        template_name=args.template,
        template_version=template_version,
    )
    if shared_count:
        sys.stdout.write(f"  → wrote {shared_count} shared scaffold files (runbooks + AI rules)\n")

    sys.stdout.write(f"  → done. Next: cd {args.project_slug} && uv sync\n")
    return 0


def _write_answers_file(
    dst: Path,
    *,
    template_name: str,
    template_version: str,
    project_slug: str,
    llm_provider: str | None,
) -> None:
    """Persist scaffold answers for `agentforge upgrade` to re-render.

    Copier's `_answers_file` directive in `copier.yml` is supposed to
    write this automatically, but doesn't reliably for in-package
    templates (bug-007). We write it ourselves with the minimum
    fields the upgrade path needs: `_template_name` so we can resolve
    the template root again, plus the four Copier variables
    (`project_name`, `project_slug`, `llm_provider`, `description`)
    so the re-render produces the same shape.
    """
    target = answers_path(dst)
    target.parent.mkdir(parents=True, exist_ok=True)
    project_name = " ".join(word.capitalize() for word in project_slug.split("-"))
    payload: dict[str, object] = {
        "_template_name": template_name,
        "_template_version": template_version,
        "project_name": project_name,
        "project_slug": project_slug,
        "llm_provider": llm_provider or "bedrock",
        "description": f"An AgentForge agent ({template_name}).",
    }
    target.write_text(
        "# AgentForge scaffold answers — DO NOT EDIT MANUALLY.\n"
        "# Used by `agentforge upgrade` to re-render managed template files.\n"
        + yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


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
