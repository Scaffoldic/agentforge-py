"""Shared scaffold injection (feat-019).

After `agentforge new` finishes Copier-rendering the chosen
template, this module copies the contents of
`agentforge.templates._shared` into the destination, rendering each
file through Jinja with the same answer context Copier saw. Each
shared file gets a marker header and an entry in the managed-files
lock — they participate in `agentforge upgrade` / `fork` exactly
like template-rendered files do.

The shared directory carries the runbooks, AGENTS.md, CLAUDE.md,
.cursorrules, and .github/copilot-instructions.md that ship with
every scaffolded agent. Putting them in one place keeps the
framework's six templates from each maintaining a near-duplicate
copy.

A `.tmpl` extension on a file marks it as Jinja-templated; the
extension is stripped on write. Files without `.tmpl` are copied
verbatim (apart from the marker header prepend).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment

from agentforge.cli._scaffold_state import (
    END_MANAGED_MARKER,
    answers_path,
    custom_section_diverged,
    hash_content,
    lock_path,
    marker_for,
    preserve_custom_section,
    read_lock,
    write_lock,
)


@dataclass
class SharedScaffoldResult:
    """Outcome of `inject_shared_scaffold`, broken down per file.

    `written` is the list of files (re)written; the other lists record
    files left untouched so callers can report — and `--dry-run` can
    preview — exactly what an upgrade would do (bug-025).
    """

    written: list[str] = field(default_factory=list)
    skipped_forked: list[str] = field(default_factory=list)
    preserved_custom: list[str] = field(default_factory=list)


def inject_shared_scaffold(
    dst: Path,
    *,
    template_name: str,
    template_version: str,
    dry_run: bool = False,
) -> SharedScaffoldResult:
    """Copy `_shared/` into the destination after Copier rendered.

    Re-injection is fork- and custom-block aware (bug-025):

    - a file the lock marks ``forked`` is **never** rewritten — its
      lock entry is left exactly as-is;
    - for a still-managed three-section file, the developer-owned
      ``<!-- agentforge:custom -->`` tail on disk is preserved while
      the managed region is refreshed from the template.

    When `dry_run` is set, nothing is written (neither files nor the
    lock); the returned result still classifies every file so callers
    can preview the plan.
    """
    result = SharedScaffoldResult()
    shared_root = _shared_root()
    if shared_root is None:
        return result

    context = _build_context(dst, template_name=template_name)
    # The shared payload is markdown / YAML / plain text — never HTML
    # rendered to a browser — so HTML escaping would actively corrupt
    # the output (e.g. `&` in code blocks becomes `&amp;`).
    env = Environment(  # nosec B701 — markdown output, not HTML
        autoescape=False,  # noqa: S701
        keep_trailing_newline=True,
    )

    lock = read_lock(dst)
    for src_path in _walk(shared_root):
        rel_path = src_path.relative_to(shared_root)
        out_rel, content = _render_one(src_path, rel_path, env, context)
        rel_key = str(out_rel)
        target = dst / out_rel

        # Respect fork status: a forked file is owned by the consumer.
        # Leave both the file and its lock entry untouched.
        existing_entry = lock.get(rel_key)
        if existing_entry and existing_entry.get("forked"):
            result.skipped_forked.append(rel_key)
            continue

        existing = target.read_text(encoding="utf-8") if target.exists() else None
        body_content = preserve_custom_section(content, existing)
        if custom_section_diverged(content, existing):
            result.preserved_custom.append(rel_key)

        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            marker = marker_for(
                target.suffix,
                f"template:{template_name}",
                template_version,
                hash_content(body_content)[:12],
            )
            body = body_content
            if marker is not None and not body_content.lstrip().startswith(marker.strip()):
                body = marker + "\n" + body_content
            target.write_text(body, encoding="utf-8")

            lock[rel_key] = {
                "hash": hash_content(body_content),
                "source_module": f"template:{template_name}:_shared",
                "source_version": template_version,
                "forked": False,
            }
        result.written.append(rel_key)

    if not dry_run:
        write_lock(dst, lock)
    return result


def _walk(root: Path) -> list[Path]:
    """Walk `root` and return every regular file path."""
    return sorted(path for path in root.rglob("*") if path.is_file())


def _render_one(
    src_path: Path,
    rel_path: Path,
    env: Environment,
    context: dict[str, Any],
) -> tuple[Path, str]:
    """Render a single shared file, returning (out_rel_path, content).

    `.tmpl`-suffixed files have the suffix stripped and are run
    through Jinja. Everything else is copied verbatim.
    """
    body = src_path.read_text(encoding="utf-8")
    if src_path.suffix == ".tmpl":
        body = env.from_string(body).render(**context)
        out_rel = rel_path.with_suffix("")  # drop `.tmpl`
    else:
        out_rel = rel_path
    if not body.endswith("\n"):
        body += "\n"
    if END_MANAGED_MARKER in body:
        # Three-section file (feat-019 chunk 1) — already terminates
        # the managed section explicitly.
        return out_rel, body
    return out_rel, body


def _build_context(dst: Path, *, template_name: str) -> dict[str, Any]:
    """Pull the Copier answer file into a Jinja context, supplementing
    with framework metadata."""
    answers = _read_answers(dst)
    return {
        "project_name": answers.get("project_name", "My Agent"),
        "project_slug": answers.get("project_slug", "my-agent"),
        "llm_provider": answers.get("llm_provider", "bedrock"),
        "description": answers.get("description", "An AgentForge agent."),
        "template_name": template_name,
        "framework_version": _framework_version(),
        "module_list": [],
    }


def _read_answers(dst: Path) -> dict[str, Any]:
    path = answers_path(dst)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): v for k, v in raw.items()}


def _framework_version() -> str:
    from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415

    try:
        # Distribution name is `agentforge-py`, not the import name
        # `agentforge` (bug-008). Do NOT change this back to "agentforge".
        return version("agentforge-py")
    except PackageNotFoundError:  # pragma: no cover
        return "0.0.0+unknown"


def _shared_root() -> Path | None:
    """Return the on-disk path of the `_shared/` template directory."""
    try:
        traversable = resources.files("agentforge.templates").joinpath("_shared")
    except ModuleNotFoundError:
        return None
    with resources.as_file(traversable) as path:
        if not path.exists() or not path.is_dir():
            return None
        return Path(path)


# Silence unused-imports warning for re-exported markers.
_ = (lock_path,)


__all__ = ["SharedScaffoldResult", "inject_shared_scaffold"]
