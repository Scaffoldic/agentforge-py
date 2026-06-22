"""Generate the packaged release-notes data from `CHANGELOG.md` (enh-006).

`agentforge upgrade --notes` prints a drift report offline against the
installed wheel, but the wheel does not ship `CHANGELOG.md`. This script
parses the repo-root `CHANGELOG.md` into the structured model
(`agentforge.cli._notes.parse_changelog`) and writes it to the committed
`release_notes.json` next to that module, which hatchling packages.

Run it whenever `CHANGELOG.md` changes; `--check` verifies the committed
JSON is current (used by the source-tree drift test / CI) without writing.

Usage:

    python scripts/gen_release_notes.py            # regenerate + write
    python scripts/gen_release_notes.py --check     # exit 1 if stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `agentforge` importable when run from a plain checkout.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "packages" / "agentforge" / "src"))

from agentforge.cli._notes import parse_changelog  # noqa: E402

_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"
_OUT = _REPO_ROOT / "packages" / "agentforge" / "src" / "agentforge" / "cli" / "release_notes.json"


def _render() -> str:
    notes = parse_changelog(_CHANGELOG.read_text(encoding="utf-8"))
    return json.dumps(notes, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed JSON is stale (no write).",
    )
    args = parser.parse_args(argv)

    rendered = _render()

    if args.check:
        current = _OUT.read_text(encoding="utf-8") if _OUT.exists() else ""
        if current != rendered:
            sys.stderr.write(
                "release_notes.json is stale — run `python scripts/gen_release_notes.py`.\n"
            )
            return 1
        sys.stdout.write("release_notes.json is up to date.\n")
        return 0

    _OUT.write_text(rendered, encoding="utf-8")
    sys.stdout.write(f"wrote {_OUT.relative_to(_REPO_ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
