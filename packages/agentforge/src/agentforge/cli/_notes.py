"""Release-notes model + drift report (enh-006 part 2).

Parses the Keep-a-Changelog `CHANGELOG.md` into a structured model, slices
it by a version range, and formats the **drift report** that
`agentforge upgrade --notes` prints — the list of fixes (and the issues
they close) plus the deprecations between a consumer's old pin and the
version they just moved to.

The parse runs at build time (`scripts/gen_release_notes.py`) and the
result is committed to `release_notes.json` next to this module, so the
report works **offline** against the installed wheel — `CHANGELOG.md`
itself is not shipped. `parse_changelog` is re-used by the generator and
by a source-tree drift test that asserts the committed JSON is current.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from typing import Any

from agentforge._deprecation import Deprecation, iter_deprecations

_VERSION_RE = re.compile(r"^##\s+\[([^\]]+)\](?:\s*[—-]+\s*(.+?))?\s*$")
_SECTION_RE = re.compile(r"^###\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^-\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*```")
_BOLD_RE = re.compile(r"^\*\*(.+?)\*\*")
# A "closes" clause + any comma-separated #NN that follow it, so
# `(closes #114, #116)` yields both. Historical phrasings vary, hence the
# alternation (closes / closed / resolves / resolved / fixes / fixed).
_CLOSES_CLAUSE_RE = re.compile(
    r"(?i)\b(?:closes?|closed|resolves?|resolved|fixes?|fixed)\b\s+"
    r"(?:issue\s+)?((?:#\d+(?:\s*,\s*)?)+)"
)
_HASHNUM_RE = re.compile(r"#(\d+)")
_REF_RE = re.compile(r"\b((?:bug|enh|feat)-\d+)\b")

_NOTES_RESOURCE = "release_notes.json"
_LABEL_MAX = 140


# ----------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------


def parse_changelog(md: str) -> dict[str, Any]:
    """Parse Keep-a-Changelog markdown into a structured notes model.

    Shape: ``{"generated_from": "CHANGELOG.md", "versions": [
    {"version", "date", "entries": {<section>: [<entry>, ...]}}]}`` where
    each entry is ``{"label", "closes": [int], "refs": [str]}``. Only
    bulleted entries under a `### Section` are captured; prose paragraphs
    and fenced code blocks are ignored for structure (but code inside a
    bullet stays part of that bullet's text).
    """
    versions: list[dict[str, Any]] = []
    cur_version: dict[str, Any] | None = None
    cur_section: str | None = None
    bullet: list[str] | None = None
    in_fence = False

    def flush() -> None:
        nonlocal bullet
        if bullet is not None and cur_version is not None and cur_section is not None:
            text = re.sub(r"\s+", " ", " ".join(bullet)).strip()
            if text:
                cur_version["entries"].setdefault(cur_section, []).append(_make_entry(text))
        bullet = None

    for raw in md.splitlines():
        if _FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            # Fenced code never contributes a label or an issue ref — a
            # `#123` or a `- ` in an example must not leak into the entry.
            # The open bullet stays open so post-fence prose still attaches.
            continue

        mv = _VERSION_RE.match(raw)
        if mv:
            flush()
            cur_version = {
                "version": mv.group(1).strip(),
                "date": (mv.group(2) or "").strip() or None,
                "entries": {},
            }
            versions.append(cur_version)
            cur_section = None
            continue

        ms = _SECTION_RE.match(raw)
        if ms:
            flush()
            cur_section = ms.group(1).strip()
            continue

        mb = _BULLET_RE.match(raw)
        if mb:
            flush()
            bullet = [mb.group(1)]
            continue

        if bullet is not None:
            bullet.append(raw)

    flush()
    return {"generated_from": "CHANGELOG.md", "versions": versions}


def _make_entry(text: str) -> dict[str, Any]:
    closes: set[int] = set()
    for clause in _CLOSES_CLAUSE_RE.findall(text):
        closes.update(int(n) for n in _HASHNUM_RE.findall(clause))
    refs = sorted(set(_REF_RE.findall(text)))
    m = _BOLD_RE.match(text)
    label = (m.group(1) if m else text).strip()
    if len(label) > _LABEL_MAX:
        label = label[: _LABEL_MAX - 1] + "…"
    return {"label": label, "closes": sorted(closes), "refs": refs}


# ----------------------------------------------------------------------
# Loading + slicing
# ----------------------------------------------------------------------


def load_notes() -> dict[str, Any]:
    """Load the committed `release_notes.json` shipped in the wheel.

    Returns an empty model if the resource is missing (e.g. a partial
    checkout before the generator has run).
    """
    try:
        raw = resources.files("agentforge.cli").joinpath(_NOTES_RESOURCE).read_text("utf-8")
    except (FileNotFoundError, ModuleNotFoundError):  # pragma: no cover - packaging guard
        return {"generated_from": "CHANGELOG.md", "versions": []}
    parsed: dict[str, Any] = json.loads(raw)
    return parsed


def _vkey(version: str) -> tuple[int, tuple[int, ...]]:
    """Sort key for a version string. `Unreleased` sorts above all releases."""
    if version.lower() == "unreleased":
        return (1, ())
    parts: list[int] = []
    for piece in version.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return (0, tuple(parts))


def slice_versions(notes: dict[str, Any], frm: str, to: str) -> list[dict[str, Any]]:
    """Versions in the half-open range ``(frm, to]`` — newer than the
    consumer's old pin, up to and including the one they moved to."""
    fk, tk = _vkey(frm), _vkey(to)
    return [v for v in notes["versions"] if fk < _vkey(v["version"]) <= tk]


def slice_deprecations(deprecations: list[Deprecation], frm: str, to: str) -> list[Deprecation]:
    fk, tk = _vkey(frm), _vkey(to)
    return [d for d in deprecations if fk < _vkey(d.since) <= tk]


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------


def format_drift_report(notes: dict[str, Any], frm: str, to: str) -> str:
    """Format the drift report for the range ``(frm, to]``.

    Lists fixes that close an issue or carry a bug/enh/feat ref, then any
    deprecations whose `since` falls in range, then a one-line summary.
    """
    versions = slice_versions(notes, frm, to)
    deprecations = slice_deprecations(iter_deprecations(), frm, to)

    fixes: list[dict[str, Any]] = [
        entry
        for ver in versions
        for entries in ver["entries"].values()
        for entry in entries
        if entry["closes"] or entry["refs"]
    ]

    out: list[str] = [f"  → drift from {frm} → {to}:", ""]

    if fixes:
        out.append("  Fixed (resolves issues you may have filed / worked around):")
        for entry in fixes:
            closes = entry["closes"]
            suffix = f"  (closes {', '.join(f'#{n}' for n in closes)})" if closes else ""
            out.append(f"    - {entry['label']}{suffix}")
        out.append("")
    else:
        out.append("  No tracked fixes in this range.")
        out.append("")

    if deprecations:
        out.append("  Deprecated (workarounds you can retire):")
        out.extend(
            f"    - {dep.qualname} → use {dep.replacement}  (since {dep.since}, {dep.ref})"
            for dep in deprecations
        )
        out.append("")

    out.append(f"  {len(fixes)} fix(es), {len(deprecations)} deprecation(s) in this range.")
    return "\n".join(out) + "\n"


__all__ = [
    "format_drift_report",
    "load_notes",
    "parse_changelog",
    "slice_deprecations",
    "slice_versions",
]
