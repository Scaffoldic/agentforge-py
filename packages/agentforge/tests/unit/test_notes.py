"""Tests for the release-notes model + drift report (enh-006 part 2)."""

from __future__ import annotations

from pathlib import Path

from agentforge.cli._notes import (
    format_drift_report,
    load_notes,
    parse_changelog,
    slice_versions,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"

_SAMPLE = """\
# Changelog

## [Unreleased]

### Fixed

- **bug-025 (P1) — upgrade clobbered files** something something.
  Continues on a second line. (closes #114)

## [0.3.0] — 2026-06-16

### Added

- **enh-003 — middleware seam.** Adds it. Closes #93.
- **enh-009 — multi close.** (closes #200, #201)

### Changed

- A plain entry with no refs or issues.

```yaml
- this is a yaml bullet inside a fence, not a changelog entry (closes #999)
```

## [0.2.4] — 2026-06-03

### Fixed

- **bug-001 — old fix.** Resolves issue #5.
"""


def test_parse_versions_and_dates() -> None:
    notes = parse_changelog(_SAMPLE)
    vs = {v["version"]: v for v in notes["versions"]}
    assert list(vs) == ["Unreleased", "0.3.0", "0.2.4"]
    assert vs["0.3.0"]["date"] == "2026-06-16"
    assert vs["Unreleased"]["date"] is None


def test_parse_extracts_closes_and_refs() -> None:
    notes = parse_changelog(_SAMPLE)
    fixed = {v["version"]: v for v in notes["versions"]}["Unreleased"]["entries"]["Fixed"]
    assert fixed[0]["closes"] == [114]
    assert fixed[0]["refs"] == ["bug-025"]
    assert fixed[0]["label"] == "bug-025 (P1) — upgrade clobbered files"  # bold lead only


def test_parse_handles_comma_separated_closes() -> None:
    notes = parse_changelog(_SAMPLE)
    added = {v["version"]: v for v in notes["versions"]}["0.3.0"]["entries"]["Added"]
    multi = next(e for e in added if "multi close" in e["label"])
    assert multi["closes"] == [200, 201]


def test_parse_ignores_bullets_inside_code_fence() -> None:
    notes = parse_changelog(_SAMPLE)
    changed = {v["version"]: v for v in notes["versions"]}["0.3.0"]["entries"]["Changed"]
    # The yaml bullet (closes #999) inside the fence must not become an entry.
    assert all(999 not in e["closes"] for e in changed)
    assert len(changed) == 1


def test_parse_alternate_resolves_phrasing() -> None:
    notes = parse_changelog(_SAMPLE)
    fixed = {v["version"]: v for v in notes["versions"]}["0.2.4"]["entries"]["Fixed"]
    assert fixed[0]["closes"] == [5]


def test_slice_versions_is_half_open_newer_than_from() -> None:
    notes = parse_changelog(_SAMPLE)
    sliced = [v["version"] for v in slice_versions(notes, "0.2.4", "0.3.0")]
    assert sliced == ["0.3.0"]  # excludes 0.2.4 (already have it), includes 0.3.0


def test_slice_includes_unreleased_only_when_targeted() -> None:
    notes = parse_changelog(_SAMPLE)
    assert "Unreleased" not in [v["version"] for v in slice_versions(notes, "0.2.4", "0.3.0")]
    assert "Unreleased" in [v["version"] for v in slice_versions(notes, "0.2.4", "Unreleased")]


def test_format_drift_report_lists_fixes_and_summary() -> None:
    notes = parse_changelog(_SAMPLE)
    report = format_drift_report(notes, "0.2.4", "Unreleased")
    assert "drift from 0.2.4 → Unreleased" in report
    assert "bug-025" in report
    assert "(closes #114)" in report
    assert "enh-003" in report  # 0.3.0 is in (0.2.4, Unreleased]
    assert "fix(es)" in report


def test_format_drift_report_empty_range() -> None:
    notes = parse_changelog(_SAMPLE)
    report = format_drift_report(notes, "0.3.0", "0.3.0")
    assert "No tracked fixes in this range." in report
    assert "0 fix(es), 0 deprecation(s)" in report


# ----------------------------------------------------------------------
# Drift guard — the committed JSON must match a fresh parse of CHANGELOG.
# ----------------------------------------------------------------------


def test_committed_release_notes_is_current() -> None:
    """`release_notes.json` is generated from `CHANGELOG.md`. If this
    fails, run `python scripts/gen_release_notes.py`."""
    fresh = parse_changelog(_CHANGELOG.read_text(encoding="utf-8"))
    committed = load_notes()
    assert committed == fresh, "release_notes.json is stale — regenerate it."


def test_real_notes_capture_known_issue_closures() -> None:
    """The real CHANGELOG's varied phrasings resolve to the right issues —
    the scenario from #115 (a 0.2.4→latest bump retires #86 / #93)."""
    notes = load_notes()
    by_ver = {v["version"]: v for v in notes["versions"]}
    closes_030 = {n for es in by_ver["0.3.0"]["entries"].values() for e in es for n in e["closes"]}
    assert {86, 92, 93} <= closes_030
