"""Unit tests for the four built-in renderers (feat-008 chunk 3).

Output formats are checked via substring assertions on stable shape
(severity / category / message / location / specific markers) rather
than byte-exact snapshots — keeps the tests robust to small whitespace
tweaks while still catching shape regressions.
"""

from __future__ import annotations

import pytest
from agentforge.findings import (
    MultiSpanFinding,
    NarrativeFinding,
    Patch,
    PatchFinding,
    SimpleFinding,
    Span,
)
from agentforge.renderers import (
    MarkdownRenderer,
    PatchApplierRenderer,
    RendererRegistry,
    ScorecardRenderer,
    SpanTableRenderer,
)
from agentforge_core.contracts.finding import Finding

# --- ScorecardRenderer (SimpleFinding) -------------------------------


def test_scorecard_text_contains_core_fields():
    f = SimpleFinding(
        severity="warning",
        category="style",
        message="Variable 'x' is unclear",
        recommendation="Rename to 'user_count'",
        file="src/foo.py",
        line=42,
        rule_id="R001",
    )
    out = ScorecardRenderer().render(f, format="text")
    assert "[warning]" in out
    assert "[R001]" in out
    assert "style:" in out
    assert "Variable 'x' is unclear" in out
    assert "src/foo.py:42" in out
    assert "Rename to 'user_count'" in out


def test_scorecard_text_handles_missing_optional_fields():
    f = SimpleFinding(severity="info", category="x", message="y")
    out = ScorecardRenderer().render(f, format="text")
    assert "[info]" in out
    assert "x:" in out
    assert "y" in out
    # No (file:line) location, no rule_id tag, no — trailer.
    assert "(" not in out
    assert "[R" not in out
    assert "—" not in out


def test_scorecard_markdown_is_a_table_row():
    f = SimpleFinding(
        severity="critical",
        category="security",
        message="API key leaked",
        file="a.py",
        line=10,
        recommendation="Rotate the key",
    )
    out = ScorecardRenderer().render(f, format="markdown")
    assert out.startswith("|")
    assert out.endswith("|")
    assert "critical" in out
    assert "security" in out
    assert "API key leaked" in out
    assert "a.py:10" in out
    assert "Rotate the key" in out


def test_scorecard_rejects_unknown_format():
    f = SimpleFinding(severity="info", category="x", message="y")
    with pytest.raises(ValueError, match="ScorecardRenderer supports"):
        ScorecardRenderer().render(f, format="html")


def test_scorecard_rejects_wrong_variant():
    f = NarrativeFinding(severity="info", category="answer", message="q", body="b")
    with pytest.raises(TypeError):
        ScorecardRenderer().render(f)


def test_scorecard_supports_simple_finding_and_subclasses():
    r = ScorecardRenderer()
    assert r.supports(SimpleFinding)
    assert not r.supports(NarrativeFinding)

    class TaggedSimple(SimpleFinding):
        pass

    assert r.supports(TaggedSimple)


# --- PatchApplierRenderer (PatchFinding) -----------------------------


def _patch_finding() -> PatchFinding:
    return PatchFinding(
        severity="suggestion",
        category="refactor",
        message="Replace deprecated `time.clock()`",
        patch=Patch(
            file="src/timer.py",
            diff="@@ -1,3 +1,3 @@\n-time.clock()\n+time.perf_counter()\n",
        ),
        rationale="`time.clock()` removed in Python 3.8.",
        confidence=0.95,
    )


def test_patch_text_includes_header_and_diff():
    out = PatchApplierRenderer().render(_patch_finding(), format="text")
    assert "[suggestion]" in out
    assert "refactor:" in out
    assert "file: src/timer.py" in out
    assert "confidence=0.95" in out
    assert "rationale: `time.clock()` removed in Python 3.8." in out
    assert "@@ -1,3 +1,3 @@" in out
    assert "+time.perf_counter()" in out


def test_patch_markdown_wraps_in_diff_fence():
    out = PatchApplierRenderer().render(_patch_finding(), format="markdown")
    assert "```diff" in out
    assert out.rstrip().endswith("```")
    # Header still present.
    assert "file: src/timer.py" in out


def test_patch_rejects_unknown_format():
    with pytest.raises(ValueError, match="PatchApplierRenderer supports"):
        PatchApplierRenderer().render(_patch_finding(), format="html")


def test_patch_rejects_wrong_variant():
    other = SimpleFinding(severity="info", category="x", message="y")
    with pytest.raises(TypeError):
        PatchApplierRenderer().render(other)


# --- MarkdownRenderer (NarrativeFinding) -----------------------------


def _narrative_finding() -> NarrativeFinding:
    return NarrativeFinding(
        severity="info",
        category="answer",
        message="How does the auth flow work?",
        body="The auth flow is...\n\nKey steps:\n1. Validate.\n2. Sign.",
        references=["src/auth.py:42", "docs/auth.md"],
    )


def test_markdown_text_format():
    out = MarkdownRenderer().render(_narrative_finding(), format="text")
    assert "How does the auth flow work?" in out
    assert "Key steps:" in out
    assert "References:" in out
    assert "src/auth.py:42" in out


def test_markdown_format_uses_heading_and_section():
    out = MarkdownRenderer().render(_narrative_finding(), format="markdown")
    assert out.startswith("## How does the auth flow work?")
    assert "### References" in out
    assert "- src/auth.py:42" in out
    assert "- docs/auth.md" in out


def test_markdown_without_references():
    f = NarrativeFinding(severity="info", category="answer", message="q", body="just the body")
    out = MarkdownRenderer().render(f, format="text")
    assert "References:" not in out
    assert "just the body" in out


def test_markdown_rejects_wrong_variant():
    with pytest.raises(TypeError):
        MarkdownRenderer().render(SimpleFinding(severity="info", category="x", message="y"))


# --- SpanTableRenderer (MultiSpanFinding) ----------------------------


def _multi_finding() -> MultiSpanFinding:
    return MultiSpanFinding(
        severity="critical",
        category="security",
        message="Hard-coded credentials in multiple files",
        spans=[
            Span(file="a.py", start_line=10, end_line=10, excerpt="API_KEY = 'abc'"),
            Span(file="b.py", start_line=22, end_line=24, excerpt="pwd = 'def'"),
        ],
        recommendation="Move to environment variables.",
    )


def test_span_table_text_one_block_per_span():
    out = SpanTableRenderer().render(_multi_finding(), format="text")
    assert "[critical]" in out
    assert "a.py:10" in out
    assert "b.py:22-24" in out
    assert "API_KEY = 'abc'" in out
    assert "pwd = 'def'" in out
    assert "recommendation: Move to environment variables." in out


def test_span_table_markdown_is_a_table():
    out = SpanTableRenderer().render(_multi_finding(), format="markdown")
    assert out.startswith("## Hard-coded credentials in multiple files")
    assert "| file | lines | excerpt |" in out
    assert "| `a.py` | 10 |" in out
    assert "| `b.py` | 22-24 |" in out
    assert "**Recommendation:** Move to environment variables." in out


def test_span_table_escapes_pipes_in_excerpt():
    f = MultiSpanFinding(
        severity="info",
        category="x",
        message="m",
        spans=[Span(file="a.py", start_line=1, end_line=1, excerpt="a | b | c")],
    )
    out = SpanTableRenderer().render(f, format="markdown")
    assert "a \\| b \\| c" in out


def test_span_table_rejects_wrong_variant():
    with pytest.raises(TypeError):
        SpanTableRenderer().render(SimpleFinding(severity="info", category="x", message="y"))


# --- RendererRegistry.default() --------------------------------------


def test_default_registry_dispatches_each_variant():
    reg = RendererRegistry.default()

    simple = SimpleFinding(severity="info", category="x", message="y")
    patch = _patch_finding()
    narrative = _narrative_finding()
    multi = _multi_finding()

    assert isinstance(reg.get(simple), ScorecardRenderer)
    assert isinstance(reg.get(patch), PatchApplierRenderer)
    assert isinstance(reg.get(narrative), MarkdownRenderer)
    assert isinstance(reg.get(multi), SpanTableRenderer)


def test_default_registry_renders_end_to_end():
    """End-to-end: build the default registry, dispatch a finding, get
    a non-empty string back."""
    reg = RendererRegistry.default()
    findings: list[Finding] = [
        SimpleFinding(severity="info", category="x", message="y"),
        _patch_finding(),
        _narrative_finding(),
        _multi_finding(),
    ]
    for f in findings:
        renderer = reg.get(f)
        text_out = renderer.render(f, format="text")
        md_out = renderer.render(f, format="markdown")
        assert isinstance(text_out, str)
        assert text_out
        assert isinstance(md_out, str)
        assert md_out


def test_default_registry_allows_override():
    """Agents replacing a built-in renderer in place: re-register the
    same variant type; the new renderer should win."""

    class CustomScorecard(ScorecardRenderer):
        def render(self, finding: Finding, format: str = "text") -> str:
            del format
            return f"CUSTOM:{finding.message}"  # type: ignore[attr-defined]

    reg = RendererRegistry.default()
    reg.register(SimpleFinding, CustomScorecard())

    f = SimpleFinding(severity="info", category="x", message="hello")
    assert reg.get(f).render(f) == "CUSTOM:hello"
