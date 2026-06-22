"""Tests for the three-section managed/custom format (feat-019 chunk 1)."""

from __future__ import annotations

from agentforge.cli._scaffold_state import (
    CUSTOM_END_MARKER,
    CUSTOM_START_MARKER,
    END_MANAGED_MARKER,
    custom_section_diverged,
    merge_three_section,
    preserve_custom_section,
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


# ----------------------------------------------------------------------
# preserve_custom_section — the bug-025 upgrade guard
# ----------------------------------------------------------------------


def test_preserve_takes_new_managed_and_existing_custom() -> None:
    new = (
        f"new managed\n\n{END_MANAGED_MARKER}\n\n"
        f"{CUSTOM_START_MARKER}\ntemplate default\n{CUSTOM_END_MARKER}\n"
    )
    existing = (
        f"old managed\n\n{END_MANAGED_MARKER}\n\n"
        f"{CUSTOM_START_MARKER}\nMY notes\n{CUSTOM_END_MARKER}\n"
    )
    out = preserve_custom_section(new, existing)
    assert "new managed" in out
    assert "MY notes" in out
    assert "template default" not in out
    assert "old managed" not in out


def test_preserve_none_existing_returns_new_verbatim() -> None:
    """A brand-new file (no existing on disk) is written whole."""
    new = f"managed\n\n{END_MANAGED_MARKER}\n\ncustom\n"
    assert preserve_custom_section(new, None) == new


def test_preserve_falls_back_when_no_markers() -> None:
    """Plain files (no end-managed marker) overwrite wholesale —
    there's no managed/custom boundary to honour."""
    new = "fresh config\n"
    existing = "stale config with local edits\n"
    assert preserve_custom_section(new, existing) == new


def test_preserve_empty_custom_uses_new_template_default() -> None:
    """When the existing custom tail is blank, the new template's
    content (including any default custom block) is used as-is."""
    new = (
        f"managed\n\n{END_MANAGED_MARKER}\n\n{CUSTOM_START_MARKER}\ndefault\n{CUSTOM_END_MARKER}\n"
    )
    existing = f"old\n\n{END_MANAGED_MARKER}\n"
    assert preserve_custom_section(new, existing) == new


def test_diverged_true_when_custom_edited() -> None:
    new = f"m\n\n{END_MANAGED_MARKER}\n\n{CUSTOM_START_MARKER}\ndefault\n{CUSTOM_END_MARKER}\n"
    existing = f"m\n\n{END_MANAGED_MARKER}\n\n{CUSTOM_START_MARKER}\nMY edit\n{CUSTOM_END_MARKER}\n"
    assert custom_section_diverged(new, existing) is True


def test_diverged_false_when_custom_matches_template() -> None:
    """An unedited file (custom tail == template default) is not flagged,
    even if managed-region whitespace differs."""
    new = (
        f"managed v2\n\n{END_MANAGED_MARKER}\n\n{CUSTOM_START_MARKER}\nsame\n{CUSTOM_END_MARKER}\n"
    )
    existing = (
        f"managed v1\n\n{END_MANAGED_MARKER}\n\n{CUSTOM_START_MARKER}\nsame\n{CUSTOM_END_MARKER}\n"
    )
    assert custom_section_diverged(new, existing) is False


def test_diverged_false_without_existing_or_markers() -> None:
    assert custom_section_diverged("x", None) is False
    assert custom_section_diverged("plain", "also plain") is False
