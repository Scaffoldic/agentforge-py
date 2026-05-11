"""Tests for the three-section managed/custom format (feat-019 chunk 1)."""

from __future__ import annotations

from agentforge.cli._scaffold_state import (
    CUSTOM_END_MARKER,
    CUSTOM_START_MARKER,
    END_MANAGED_MARKER,
    merge_three_section,
    split_three_section,
)


def test_split_no_marker_treats_all_as_managed() -> None:
    managed, custom = split_three_section("just content with no marker")
    assert managed == "just content with no marker"
    assert custom == ""


def test_split_with_marker_splits_correctly() -> None:
    raw = (
        "# Runbook\n\n"
        "managed body\n\n"
        f"{END_MANAGED_MARKER}\n\n"
        f"{CUSTOM_START_MARKER}\n"
        "developer notes\n"
        f"{CUSTOM_END_MARKER}\n"
    )
    managed, custom = split_three_section(raw)
    assert managed.endswith(END_MANAGED_MARKER)
    assert "developer notes" in custom
    assert "managed body" in managed


def test_merge_preserves_custom_section() -> None:
    new_managed = f"# Runbook v2\n\nnew managed body\n\n{END_MANAGED_MARKER}"
    existing_custom = f"\n\n{CUSTOM_START_MARKER}\npreserved notes\n{CUSTOM_END_MARKER}\n"
    merged = merge_three_section(new_managed, existing_custom)
    assert "new managed body" in merged
    assert "preserved notes" in merged
    assert merged.count(END_MANAGED_MARKER) == 1


def test_merge_appends_marker_when_missing() -> None:
    """When the new managed body forgets the marker, merge_three_section
    adds one so downstream split calls still work."""
    new_managed = "# Runbook\n\nbody without marker"
    merged = merge_three_section(new_managed, "\n\ncustom tail\n")
    assert END_MANAGED_MARKER in merged
    assert "custom tail" in merged


def test_roundtrip_preserves_content() -> None:
    """Split → merge round-trips."""
    original = (
        "# Runbook 02 — Add a Tool\n\n"
        "Step 1...\n"
        f"\n{END_MANAGED_MARKER}\n\n"
        f"{CUSTOM_START_MARKER}\n"
        "Our team prefers X over Y.\n"
        f"{CUSTOM_END_MARKER}\n"
    )
    managed, custom = split_three_section(original)
    re_merged = merge_three_section(managed, custom)
    assert "Step 1..." in re_merged
    assert "Our team prefers X over Y." in re_merged
