"""Lock-file + marker-header machinery for feat-011 chunks 3-5.

State layout (per spec §4.2):

    .agentforge-state/
    ├── answers.yml          # Copier answers, written by Copier itself
    └── managed-files.lock   # { path: { hash, source_module,
                                         source_version,
                                         forked: bool } }

Marker header form (per spec §4.2):

    AGENTFORGE-MANAGED: <module>@<version> hash:<sha256-prefix>

Where `<module>` is `template:<template-name>` for files from
`agentforge new`, or `<distribution>` for files from
`agentforge add module`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml
from agentforge_core.production.exceptions import ModuleError

_STATE_DIR = Path(".agentforge-state")
_LOCK_FILE = _STATE_DIR / "managed-files.lock"
_ANSWERS_FILE = _STATE_DIR / "answers.yml"

_MARKER_PREFIX = "AGENTFORGE-MANAGED:"
_HASH_PREFIX_LEN = 12


def lock_path(cwd: Path) -> Path:
    return cwd / _LOCK_FILE


def answers_path(cwd: Path) -> Path:
    return cwd / _ANSWERS_FILE


def read_lock(cwd: Path) -> dict[str, dict[str, Any]]:
    """Read the managed-files lock. Empty dict if absent."""
    path = lock_path(cwd)
    if not path.exists():
        return {}
    with path.open() as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ModuleError(f"{path} must be a top-level mapping; got {type(raw).__name__}.")
    return raw


def write_lock(cwd: Path, lock: dict[str, dict[str, Any]]) -> None:
    """Write the managed-files lock; creates the state dir."""
    path = lock_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        yaml.safe_dump(lock, fh, sort_keys=True)


def hash_content(content: str) -> str:
    """sha256 of `content` UTF-8 encoded. Caller takes a prefix."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def marker_for(
    suffix: str, source_module: str, source_version: str, hash_prefix: str
) -> str | None:
    """Format the marker header line for a file with the given suffix.

    Returns `None` for file extensions where comment markers aren't
    practical (e.g. binary). Suffixes follow the same per-language
    mapping as feat-010b's manifest applier.
    """
    body = f"{_MARKER_PREFIX} {source_module}@{source_version} hash:{hash_prefix}"
    if suffix in {".py", ".sh", ".yaml", ".yml", ".toml", ".ini", ".env", ".sql", ".cfg"}:
        return f"# {body}"
    if suffix in {".js", ".ts", ".tsx", ".jsx", ".css"}:
        return f"// {body}"
    if suffix in {".html", ".xml", ".md"}:
        return f"<!-- {body} -->"
    return None


def write_managed_files_lock(
    cwd: Path,
    *,
    template_name: str,
    template_version: str,
    rendered_root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Walk `cwd`, write a lock entry for every framework-managed
    file, return the lock dict.

    `rendered_root` defaults to `cwd`; pass a different path when
    running against a Copier-rendered scaffold that isn't the cwd.

    Files counted as "managed" are every file the template produced.
    Identification is by the framework marker header: any file with
    the `AGENTFORGE-MANAGED:` line at the top counts. For the
    initial scaffold (no markers yet), the caller writes the lock
    from the Copier render's file list — see `prepend_markers`.
    """
    root = rendered_root if rendered_root is not None else cwd
    lock: dict[str, dict[str, Any]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        # Skip the state dir itself.
        if rel.parts and rel.parts[0] == _STATE_DIR.name:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable — skip
        h = hash_content(content)
        lock[str(rel).replace("\\", "/")] = {
            "hash": h,
            "source_module": f"template:{template_name}",
            "source_version": template_version,
            "forked": False,
        }
    write_lock(cwd, lock)
    return lock


def prepend_markers(
    cwd: Path,
    *,
    template_name: str,
    template_version: str,
) -> None:
    """For every file in the lock that supports a comment-marker
    extension, prepend `# AGENTFORGE-MANAGED: ...` if not already
    present. Idempotent."""
    lock = read_lock(cwd)
    for rel_path, entry in lock.items():
        path = cwd / rel_path
        if not path.exists():
            continue
        suffix = path.suffix
        marker = marker_for(
            suffix,
            entry.get("source_module", f"template:{template_name}"),
            entry.get("source_version", template_version),
            entry["hash"][:_HASH_PREFIX_LEN],
        )
        if marker is None:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if _MARKER_PREFIX in content.split("\n", 1)[0]:
            continue  # already marked
        path.write_text(marker + "\n" + content, encoding="utf-8")


def strip_marker(path: Path) -> bool:
    """Strip the framework marker header (if present) from `path`.

    Returns True if a marker was stripped. Used by `agentforge fork`.
    """
    if not path.exists():
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    lines = content.split("\n", 1)
    if not lines or _MARKER_PREFIX not in lines[0]:
        return False
    rest = lines[1] if len(lines) > 1 else ""
    path.write_text(rest, encoding="utf-8")
    return True


def file_status(cwd: Path, rel_path: str, entry: dict[str, Any]) -> str:
    """Classify a tracked file as 'managed', 'forked', 'drifted', or
    'missing'."""
    if entry.get("forked"):
        return "forked"
    path = cwd / rel_path
    if not path.exists():
        return "missing"
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return "managed"
    # Strip the framework marker line before hashing — markers
    # change the bytes-on-disk but not the underlying content.
    body = _strip_marker_for_hash(content)
    if hash_content(body) == entry["hash"]:
        return "managed"
    return "drifted"


def _strip_marker_for_hash(content: str) -> str:
    """Drop the leading AGENTFORGE-MANAGED line for hash comparison."""
    if _MARKER_PREFIX not in content.split("\n", 1)[0]:
        return content
    parts = content.split("\n", 1)
    return parts[1] if len(parts) > 1 else ""


# ----------------------------------------------------------------------
# Three-section managed / custom format (feat-019)
# ----------------------------------------------------------------------

END_MANAGED_MARKER = "<!-- agentforge:end-managed -->"
"""Closes the framework-managed section. Anything after this marker is
developer-owned (the custom section) and survives upgrades."""

CUSTOM_START_MARKER = "<!-- agentforge:custom -->"
CUSTOM_END_MARKER = "<!-- agentforge:end-custom -->"


def split_three_section(content: str) -> tuple[str, str]:
    """Split markdown / text content into (managed, custom).

    The managed section is everything up to and including the
    `<!-- agentforge:end-managed -->` marker. The custom section is
    everything after that. Returns (managed, custom). When the marker
    is absent, the entire content is treated as managed.
    """
    if END_MANAGED_MARKER not in content:
        return content, ""
    head, _, tail = content.partition(END_MANAGED_MARKER)
    managed = head + END_MANAGED_MARKER
    custom = tail
    return managed, custom


def merge_three_section(new_managed: str, existing_custom: str) -> str:
    """Stitch a freshly rendered managed section onto a preserved
    custom section.

    `new_managed` should already include the `END_MANAGED_MARKER`. If
    it doesn't, the marker is appended so the on-disk file remains
    parseable by future `split_three_section` calls.
    """
    managed = new_managed
    if END_MANAGED_MARKER not in managed:
        managed = managed.rstrip() + "\n\n" + END_MANAGED_MARKER + "\n"
    return managed.rstrip() + "\n" + existing_custom.lstrip("\n")
