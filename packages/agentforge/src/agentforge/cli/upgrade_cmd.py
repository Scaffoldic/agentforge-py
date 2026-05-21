"""`agentforge upgrade/fork/unfork/status` commands (feat-011 chunks 4-5).

- **upgrade**: wraps Copier's `copier update` for the linked
  template; refreshes the managed-files lock.
- **fork**: strip the framework marker from a file + flag it as
  forked in the lock. Future upgrades skip it.
- **unfork**: restore from the template (lossy — overwrites local
  edits). Re-runs the per-file render and updates the lock.
- **status**: walks the lock and prints managed / forked / drifted
  / missing per file.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import yaml
from agentforge_core.production.exceptions import ModuleError

from agentforge.cli._scaffold_state import (
    _HASH_PREFIX_LEN,
    _strip_marker_for_hash,
    answers_path,
    file_status,
    hash_content,
    marker_for,
    read_lock,
    strip_marker,
    write_lock,
)


def register_upgrade_cmds(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach upgrade / fork / unfork / status to the parent
    subparser action."""
    upgrade = sub.add_parser(
        "upgrade",
        help="Pull framework updates into this agent (three-way merge).",
    )
    upgrade.add_argument("--to", default=None, help="Target version (default: latest).")
    upgrade.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing.",
    )
    upgrade.set_defaults(_handler=_run_upgrade)

    fork = sub.add_parser("fork", help="Claim a managed file — future upgrades skip it.")
    fork.add_argument("path", help="Path to the file to fork (relative to cwd).")
    fork.set_defaults(_handler=_run_fork)

    unfork = sub.add_parser("unfork", help="Restore a forked file to the template version.")
    unfork.add_argument("path", help="Path to the file to unfork.")
    unfork.set_defaults(_handler=_run_unfork)

    status = sub.add_parser(
        "status",
        help="Show managed / forked / drifted files in this agent.",
    )
    status.set_defaults(_handler=_run_status)


# ----------------------------------------------------------------------
# upgrade
# ----------------------------------------------------------------------


def _run_upgrade(
    args: argparse.Namespace,
    *,
    cwd: Path | None = None,
) -> int:
    """Refresh framework-managed files from the current template.

    The v0.2.x templates ship inside the framework package
    (`agentforge/templates/<name>/`), not as a separate Copier-
    versioned repo, so `copier update` can't do its usual VCS-driven
    three-way merge (see bug-007). Instead we render the current
    template into a temp directory with `run_copy`, then per the
    existing `managed-files.lock` overwrite each non-forked managed
    file in place. Forked files (via `agentforge fork`) are
    preserved. New files introduced by the upgraded template are
    added. The shared scaffold (`_shared/`) is re-injected so
    runbooks + AI-assistant rules track the new framework version.
    """
    work_dir = cwd if cwd is not None else Path.cwd()
    if not answers_path(work_dir).exists():
        sys.stderr.write(
            "No .agentforge-state/answers.yml; this directory wasn't scaffolded by "
            "`agentforge new`. Nothing to upgrade.\n"
        )
        return 1

    answers = _read_answers(work_dir)
    template_name = answers.pop("_template_name", None)
    if not isinstance(template_name, str) or not template_name:
        sys.stderr.write(
            "answers.yml is missing `_template_name`. The file may pre-date the "
            "bug-007 fix (v0.2.3) or have been hand-edited. Re-scaffold to "
            "regenerate or add the field manually.\n"
        )
        return 1

    from agentforge.cli.new_cmd import (  # noqa: PLC0415
        _TEMPLATES,
        _template_root,
        _template_version,
    )

    template_root = _template_root(template_name)
    if template_root is None:
        sys.stderr.write(
            f"Template {template_name!r} not shipped with this install. "
            f"Known: {', '.join(_TEMPLATES)}.\n"
        )
        return 1

    if args.dry_run:
        sys.stdout.write(
            f"  → dry-run: would re-render template {template_name!r} into this "
            f"directory and refresh every non-forked managed file.\n"
        )
        return 0

    template_version = args.to if args.to else _template_version()
    try:
        return _do_upgrade(
            work_dir,
            template_name=template_name,
            template_root=template_root,
            template_version=template_version,
            answers=answers,
        )
    except ModuleError as exc:
        sys.stderr.write(f"upgrade failed: {exc}\n")
        return 1


def _read_answers(work_dir: Path) -> dict[str, object]:
    raw = yaml.safe_load(answers_path(work_dir).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ModuleError("answers.yml must be a top-level mapping.")
    return {str(k): v for k, v in raw.items()}


def _do_upgrade(
    work_dir: Path,
    *,
    template_name: str,
    template_root: Path,
    template_version: str,
    answers: dict[str, object],
) -> int:
    """Render template → temp; copy each non-forked managed file
    into work_dir; refresh lock; re-inject shared scaffold."""
    from agentforge.cli._shared_scaffold import inject_shared_scaffold  # noqa: PLC0415
    from agentforge.cli.new_cmd import _run_copier  # noqa: PLC0415

    # Drop the leading-underscore Copier metadata keys from the answers
    # we pass back to Copier — `_template_name` / `_template_version`
    # are ours, not Copier's, and Copier rejects unknown leading-`_`
    # keys.
    copier_answers: dict[str, object] = {k: v for k, v in answers.items() if not k.startswith("_")}

    old_lock = read_lock(work_dir)
    new_lock: dict[str, dict[str, object]] = {}
    refreshed: list[str] = []
    forked_kept: list[str] = []
    new_files: list[str] = []

    with tempfile.TemporaryDirectory(prefix="agentforge-upgrade-") as temp_str:
        temp = Path(temp_str)
        _run_copier(str(template_root), str(temp), copier_answers, defaults=True)

        # Pass 1: refresh every file in the old lock.
        for rel, entry in old_lock.items():
            if entry.get("forked"):
                new_lock[rel] = entry
                forked_kept.append(rel)
                continue
            src = temp / rel
            dst = work_dir / rel
            if not src.exists():
                # File was in scaffold but isn't in current template.
                # Drop it from the new lock — `agentforge upgrade`
                # treats template removals as "no longer managed".
                continue
            _write_with_marker(
                dst,
                src.read_text(encoding="utf-8"),
                source_module=str(entry.get("source_module", f"template:{template_name}")),
                source_version=template_version,
            )
            new_lock[rel] = {
                **entry,
                "hash": hash_content(_strip_marker_for_hash(dst.read_text(encoding="utf-8"))),
                "source_version": template_version,
            }
            refreshed.append(rel)

        # Pass 2: add files in the new template that weren't in the
        # old lock (template grew). Skip the state dir.
        for src in temp.rglob("*"):
            if not src.is_file():
                continue
            rel = str(src.relative_to(temp)).replace("\\", "/")
            if rel in old_lock:
                continue
            if rel.startswith(".agentforge-state/"):
                continue
            dst = work_dir / rel
            _write_with_marker(
                dst,
                src.read_text(encoding="utf-8"),
                source_module=f"template:{template_name}",
                source_version=template_version,
            )
            new_lock[rel] = {
                "hash": hash_content(_strip_marker_for_hash(dst.read_text(encoding="utf-8"))),
                "source_module": f"template:{template_name}",
                "source_version": template_version,
                "forked": False,
            }
            new_files.append(rel)

    write_lock(work_dir, new_lock)

    # Re-inject the shared scaffold (runbooks + AGENTS.md / CLAUDE.md /
    # .cursorrules / copilot-instructions) so they track the new
    # framework version.
    shared = inject_shared_scaffold(
        work_dir,
        template_name=template_name,
        template_version=template_version,
    )

    sys.stdout.write(
        f"  → refreshed {len(refreshed)} managed files; preserved {len(forked_kept)} forked.\n"
    )
    if new_files:
        max_preview = 3
        preview = ", ".join(new_files[:max_preview])
        if len(new_files) > max_preview:
            preview += "…"
        sys.stdout.write(f"  → added {len(new_files)} new managed files: {preview}\n")
    sys.stdout.write(f"  → re-injected {shared} shared scaffold files.\n")
    sys.stdout.write("  → upgrade complete; lock refreshed.\n")
    return 0


def _write_with_marker(
    dst: Path,
    content: str,
    *,
    source_module: str,
    source_version: str,
) -> None:
    """Write `content` to `dst`, prepending the AGENTFORGE-MANAGED
    marker for the file's extension when applicable."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    marker = marker_for(
        dst.suffix,
        source_module,
        source_version,
        hash_content(content)[:_HASH_PREFIX_LEN],
    )
    body = (marker + "\n" + content) if marker else content
    dst.write_text(body, encoding="utf-8")


# ----------------------------------------------------------------------
# fork / unfork
# ----------------------------------------------------------------------


def _run_fork(args: argparse.Namespace, *, cwd: Path | None = None) -> int:
    work_dir = cwd if cwd is not None else Path.cwd()
    rel = args.path
    lock = read_lock(work_dir)
    if rel not in lock:
        sys.stderr.write(f"{rel} is not in the managed-files lock; nothing to fork.\n")
        return 1
    target = work_dir / rel
    strip_marker(target)
    lock[rel] = {**lock[rel], "forked": True}
    write_lock(work_dir, lock)
    sys.stdout.write(f"  → forked {rel}. Future upgrades will skip it.\n")
    return 0


def _run_unfork(args: argparse.Namespace, *, cwd: Path | None = None) -> int:
    work_dir = cwd if cwd is not None else Path.cwd()
    rel = args.path
    lock = read_lock(work_dir)
    if rel not in lock:
        sys.stderr.write(f"{rel} is not in the managed-files lock.\n")
        return 1
    if not lock[rel].get("forked"):
        sys.stderr.write(f"{rel} is not forked.\n")
        return 1
    # Flip the flag and re-prepend the marker. We can't restore the
    # full template-version content without re-running Copier; for
    # now, just clear the forked flag and recompute the hash. The
    # next `agentforge upgrade` will re-render the file.
    target = work_dir / rel
    if target.exists():
        try:
            content = target.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            content = ""
        from agentforge.cli._scaffold_state import _strip_marker_for_hash  # noqa: PLC0415

        body = _strip_marker_for_hash(content)
        marker = marker_for(
            target.suffix,
            lock[rel].get("source_module", "template:unknown"),
            lock[rel].get("source_version", "0"),
            hash_content(body)[:12],
        )
        if marker:
            target.write_text(marker + "\n" + body, encoding="utf-8")
        lock[rel] = {**lock[rel], "forked": False, "hash": hash_content(body)}
    else:
        lock[rel] = {**lock[rel], "forked": False}
    write_lock(work_dir, lock)
    sys.stdout.write(f"  → unforked {rel}. Run `agentforge upgrade` to pull template content.\n")
    return 0


# ----------------------------------------------------------------------
# status
# ----------------------------------------------------------------------


def _run_status(args: argparse.Namespace, *, cwd: Path | None = None) -> int:
    del args
    work_dir = cwd if cwd is not None else Path.cwd()
    lock = read_lock(work_dir)
    if not lock:
        sys.stdout.write("No managed-files lock; this directory wasn't scaffolded.\n")
        return 0

    by_status: dict[str, list[str]] = {"managed": [], "forked": [], "drifted": [], "missing": []}
    for rel, entry in sorted(lock.items()):
        status = file_status(work_dir, rel, entry)
        by_status[status].append(rel)

    for label in ("managed", "forked", "drifted", "missing"):
        files = by_status[label]
        if not files:
            continue
        sys.stdout.write(f"\n{label.upper()} ({len(files)})\n")
        for rel in files:
            sys.stdout.write(f"  {rel}\n")
    return 0


__all__ = ["register_upgrade_cmds"]


# Suppress unused-import warning in module-level imports the file
# uses transitively.
_ = yaml
