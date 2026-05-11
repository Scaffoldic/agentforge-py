"""`agentforge docs` — open and audit runbooks (feat-019 chunk 7).

Four subcommands:

- `docs` — interactive picker (lists every runbook, prompts for
  the one to open).
- `docs <topic>` — open by name. Matches filename stem (e.g.
  `02-add-a-tool`), bare number (`2`), or alias (`add-tool`,
  `add-mcp`).
- `docs check` — diff local runbook content against the
  framework's current bundle; report drift; suggest
  `agentforge upgrade`.
- `docs serve` — local HTTP browser of the runbook tree.

The runbooks live under `docs/runbooks/` relative to the
project's working directory (overrideable via
`agentforge.yaml > docs.runbooks_path`). The framework's bundled
copies live inside the `agentforge` wheel — `docs check`
compares the two.
"""

from __future__ import annotations

import argparse
import http.server
import os
import re
import socketserver
import subprocess  # nosec B404 — opens user-chosen $EDITOR; argv list, no shell
import sys
from importlib import resources
from pathlib import Path

from agentforge.cli._scaffold_state import _strip_marker_for_hash, hash_content


def register_docs_cmd(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach `agentforge docs` to the parent subparser action."""
    parser = sub.add_parser(
        "docs",
        help="Open / list / audit project runbooks.",
        description="Open and audit AgentForge runbooks shipped into this project.",
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help=(
            "Runbook to open. Matches filename stem (02-add-a-tool), "
            "bare number (2), or alias (add-tool / add-memory)."
        ),
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Override the runbooks directory (default: ./docs/runbooks).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare local runbooks against the framework's bundle; report drift.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start a local HTTP browser of the runbook tree on port 8765.",
    )
    parser.set_defaults(_handler=_run_docs)


def _run_docs(args: argparse.Namespace) -> int:
    runbooks_dir = args.path if args.path is not None else Path.cwd() / "docs" / "runbooks"
    if not runbooks_dir.exists():
        sys.stderr.write(
            f"agentforge docs: {runbooks_dir} does not exist. "
            "Scaffold via `agentforge new` to install runbooks.\n"
        )
        return 1
    if args.check:
        return _do_check(runbooks_dir)
    if args.serve:
        return _do_serve(runbooks_dir)
    if args.topic is None:
        return _do_list(runbooks_dir)
    return _do_open(runbooks_dir, args.topic)


def _do_list(runbooks_dir: Path) -> int:
    """Print every runbook in numeric order."""
    for runbook in _scan(runbooks_dir):
        print(f"  {runbook.stem:<40}  {runbook}")
    return 0


def _do_open(runbooks_dir: Path, topic: str) -> int:
    """Resolve `topic` to a single runbook and open it via $EDITOR / less."""
    match = _resolve_topic(runbooks_dir, topic)
    if match is None:
        sys.stderr.write(
            f"agentforge docs: no runbook matches {topic!r}. Try `agentforge docs` to list.\n"
        )
        return 1
    editor = os.environ.get("EDITOR")
    if editor:
        return subprocess.run(  # noqa: S603  # nosec B603 — $EDITOR is user's own
            [editor, str(match)],
            check=False,
        ).returncode
    # No EDITOR — print to stdout so the developer can pipe to less.
    sys.stdout.write(match.read_text(encoding="utf-8"))
    return 0


def _do_check(runbooks_dir: Path) -> int:
    """Diff local runbook hashes against the framework's bundle."""
    bundled = _bundled_runbooks_dir()
    if bundled is None:
        sys.stderr.write(
            "agentforge docs check: framework bundle not found — "
            "running from a non-standard install?\n"
        )
        return 1
    drift: list[str] = []
    for local in _scan(runbooks_dir):
        rel = local.relative_to(runbooks_dir)
        # Bundled file may carry `.tmpl` suffix; check both.
        candidates = [bundled / rel, bundled / (str(rel) + ".tmpl")]
        bundled_path = next((c for c in candidates if c.exists()), None)
        if bundled_path is None:
            drift.append(f"  +local  {rel}")
            continue
        local_hash = hash_content(_strip_marker_for_hash(local.read_text(encoding="utf-8")))
        bundled_hash = hash_content(bundled_path.read_text(encoding="utf-8"))
        if local_hash != bundled_hash:
            drift.append(f"  ~drift  {rel}")
    if drift:
        print("Runbook drift detected:")
        for line in drift:
            print(line)
        print("\nRun `agentforge upgrade` to merge framework updates.")
        return 1
    print("All runbooks in sync with framework bundle.")
    return 0


def _do_serve(runbooks_dir: Path, port: int = 8765) -> int:
    """Start a basic HTTP server over the runbooks directory."""
    handler_cls = http.server.SimpleHTTPRequestHandler
    cwd = os.getcwd()
    os.chdir(runbooks_dir)
    try:
        with socketserver.TCPServer(("127.0.0.1", port), handler_cls) as httpd:
            sys.stdout.write(
                f"agentforge docs: serving {runbooks_dir} at http://127.0.0.1:{port}/\n"
                "Press Ctrl-C to stop.\n"
            )
            httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\nstopped.\n")
    finally:
        os.chdir(cwd)
    return 0


def _scan(runbooks_dir: Path) -> list[Path]:
    """Walk the runbooks directory and return numbered runbooks in order."""
    return sorted(p for p in runbooks_dir.glob("*.md") if _RUNBOOK_RE.match(p.name))


_RUNBOOK_RE = re.compile(r"^\d{2}-[a-z0-9-]+\.md$")


def _resolve_topic(runbooks_dir: Path, topic: str) -> Path | None:
    """Resolve `topic` to a runbook path.

    Match precedence:
    1. Exact filename stem (`02-add-a-tool`).
    2. Bare number (`2` → `02-...`).
    3. Alias (`add-tool` → matches any runbook whose body
       (after the leading number) contains the alias).
    """
    if topic.endswith(".md"):
        candidate = runbooks_dir / topic
        if candidate.exists():
            return candidate
    candidate = runbooks_dir / f"{topic}.md"
    if candidate.exists():
        return candidate
    if topic.isdigit():
        num = f"{int(topic):02d}-"
        for p in _scan(runbooks_dir):
            if p.name.startswith(num):
                return p
    for p in _scan(runbooks_dir):
        # Drop the `NN-` prefix when comparing aliases.
        body = p.stem.split("-", 1)[1] if "-" in p.stem else p.stem
        if topic in body:
            return p
    return None


def _bundled_runbooks_dir() -> Path | None:
    """Return the on-disk path of the framework's bundled runbooks."""
    try:
        traversable = resources.files("agentforge.templates").joinpath(
            "_shared", "docs", "runbooks"
        )
    except ModuleNotFoundError:
        return None
    with resources.as_file(traversable) as path:
        if not path.exists() or not path.is_dir():
            return None
        return Path(path)


__all__ = ["register_docs_cmd"]
