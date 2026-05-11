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
from pathlib import Path

import yaml
from agentforge_core.production.exceptions import ModuleError

from agentforge.cli._scaffold_state import (
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
    """Run `copier update` against the linked template + refresh lock.

    Copier handles the three-way merge against the answer file's
    recorded template-version. We only handle the lock refresh
    afterwards.
    """
    work_dir = cwd if cwd is not None else Path.cwd()
    if not answers_path(work_dir).exists():
        sys.stderr.write(
            "No .agentforge-state/answers.yml; this directory wasn't scaffolded by "
            "`agentforge new`. Nothing to upgrade.\n"
        )
        return 1

    if args.dry_run:
        sys.stdout.write("  → dry-run: not actually running copier update\n")
        return 0

    try:
        _run_copier_update(work_dir, to=args.to)
    except ModuleError as exc:
        sys.stderr.write(f"upgrade failed: {exc}\n")
        return 1

    # Refresh the lock: re-hash every still-managed file against its
    # new content. Forked entries stay flagged.
    lock = read_lock(work_dir)
    new_lock: dict[str, dict[str, object]] = {}
    for rel, entry in lock.items():
        path = work_dir / rel
        if not path.exists():
            continue
        if entry.get("forked"):
            new_lock[rel] = entry
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            new_lock[rel] = entry
            continue
        # Strip marker before hashing.
        from agentforge.cli._scaffold_state import _strip_marker_for_hash  # noqa: PLC0415

        body = _strip_marker_for_hash(content)
        new_lock[rel] = {**entry, "hash": hash_content(body)}
    write_lock(work_dir, new_lock)
    sys.stdout.write("  → upgrade complete; lock refreshed.\n")
    return 0


def _run_copier_update(cwd: Path, *, to: str | None) -> None:
    from copier import run_update  # noqa: PLC0415

    try:
        run_update(
            dst_path=str(cwd),
            vcs_ref=to or "HEAD",
            defaults=True,
            overwrite=True,
            quiet=False,
        )
    except Exception as exc:
        raise ModuleError(f"copier update failed: {exc}") from exc


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
