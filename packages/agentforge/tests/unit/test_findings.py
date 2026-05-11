"""Unit tests for `agentforge.findings` (feat-008 chunk 1).

Coverage:
  - Each shipped variant satisfies the `Finding` Protocol structurally
    (runtime `isinstance` check works).
  - Frozen-ness: mutation raises `ValidationError`.
  - `to_dict()` produces JSON-serialisable output.
  - `from_dict()` round-trips a `to_dict()` payload back to an equal
    instance.
  - Field validation: required fields, range constraints, span
    line-order invariant.
"""

from __future__ import annotations

import json

import agentforge as af
import pytest
from agentforge.findings import (
    MultiSpanFinding,
    NarrativeFinding,
    Patch,
    PatchFinding,
    SimpleFinding,
    Span,
)
from agentforge_core.contracts.finding import Finding
from pydantic import BaseModel, ValidationError

# --- helpers ----------------------------------------------------------


def _simple() -> SimpleFinding:
    return SimpleFinding(
        severity="warning",
        category="style",
        message="Variable 'x' is unclear",
        recommendation="Rename to 'user_count'",
        file="src/foo.py",
        line=42,
        rule_id="R001",
        metadata={"tags": ["readability"]},
    )


def _patch() -> PatchFinding:
    return PatchFinding(
        severity="suggestion",
        category="refactor",
        message="Replace deprecated `time.clock()`",
        patch=Patch(
            file="src/timer.py",
            diff="@@ -1,3 +1,3 @@\n-time.clock()\n+time.perf_counter()\n",
            hunk_count=1,
        ),
        rationale="`time.clock()` removed in Python 3.8.",
        confidence=0.95,
    )


def _narrative() -> NarrativeFinding:
    return NarrativeFinding(
        severity="info",
        category="answer",
        message="How does the auth flow work?",
        body="The auth flow is...\n\nKey steps:\n1. Validate.\n2. Sign.",
        references=["src/auth.py:42", "docs/auth.md"],
    )


def _multi() -> MultiSpanFinding:
    return MultiSpanFinding(
        severity="critical",
        category="security",
        message="Hard-coded credentials in multiple files",
        spans=[
            Span(file="a.py", start_line=10, end_line=10, excerpt="API_KEY = 'abc'"),
            Span(file="b.py", start_line=22, end_line=24, excerpt="..."),
        ],
        recommendation="Move to environment variables.",
    )


# --- Protocol conformance --------------------------------------------


@pytest.mark.parametrize(
    "factory",
    [_simple, _patch, _narrative, _multi],
)
def test_variant_satisfies_finding_protocol(factory):
    instance = factory()
    assert isinstance(instance, Finding)


def test_custom_pydantic_variant_satisfies_protocol():
    """The Protocol is structural — third-party variants don't need to
    subclass `_FindingBase`. A bare Pydantic model with the three
    Protocol attrs and a `to_dict` method should pass `isinstance`."""

    class CoverageFinding(BaseModel):
        severity: str
        category: str = "coverage"
        message: str = ""
        coverage_pct: float = 0.0

        def to_dict(self) -> dict[str, object]:
            return self.model_dump(mode="json")

    f = CoverageFinding(severity="warning", message="Below threshold", coverage_pct=72.5)
    assert isinstance(f, Finding)


# --- frozen-ness ------------------------------------------------------


def test_simple_finding_is_frozen():
    f = _simple()
    with pytest.raises(ValidationError):
        f.severity = "critical"  # type: ignore[misc]


def test_patch_helper_is_frozen():
    p = Patch(file="x.py", diff="@@ -1 +1 @@\n-a\n+b\n")
    with pytest.raises(ValidationError):
        p.file = "y.py"  # type: ignore[misc]


def test_span_helper_is_frozen():
    s = Span(file="x.py", start_line=1, end_line=2)
    with pytest.raises(ValidationError):
        s.start_line = 99  # type: ignore[misc]


# --- to_dict / from_dict round-trip ----------------------------------


@pytest.mark.parametrize(
    ("factory", "cls"),
    [
        (_simple, SimpleFinding),
        (_patch, PatchFinding),
        (_narrative, NarrativeFinding),
        (_multi, MultiSpanFinding),
    ],
)
def test_round_trip(factory, cls):
    original = factory()
    serialised = original.to_dict()

    # JSON-serialisable.
    text = json.dumps(serialised)
    revived = cls.from_dict(json.loads(text))

    assert revived == original


def test_to_dict_is_json_compatible_nested_models():
    """`Patch` and `Span` nested inside variants must serialise to
    plain dicts, not Pydantic model instances."""
    p = _patch()
    d = p.to_dict()
    assert isinstance(d["patch"], dict)
    assert d["patch"]["file"] == "src/timer.py"

    m = _multi()
    d2 = m.to_dict()
    assert isinstance(d2["spans"], list)
    assert all(isinstance(s, dict) for s in d2["spans"])


# --- field validation -------------------------------------------------


def test_simple_finding_rejects_empty_required_fields():
    with pytest.raises(ValidationError):
        SimpleFinding(severity="", category="style", message="x")
    with pytest.raises(ValidationError):
        SimpleFinding(severity="warning", category="", message="x")
    with pytest.raises(ValidationError):
        SimpleFinding(severity="warning", category="style", message="")


def test_patch_finding_confidence_range():
    base = {
        "severity": "info",
        "category": "x",
        "message": "y",
        "patch": Patch(file="a.py", diff="@@ -1 +1 @@\n-a\n+b\n"),
        "rationale": "r",
    }
    with pytest.raises(ValidationError):
        PatchFinding(**base, confidence=-0.1)
    with pytest.raises(ValidationError):
        PatchFinding(**base, confidence=1.5)
    PatchFinding(**base, confidence=0.0)  # boundary
    PatchFinding(**base, confidence=1.0)


def test_multi_span_finding_requires_at_least_one_span():
    with pytest.raises(ValidationError):
        MultiSpanFinding(
            severity="critical",
            category="security",
            message="x",
            spans=[],
        )


def test_span_end_line_must_be_at_or_after_start_line():
    Span(file="x.py", start_line=10, end_line=10)  # ok — single line
    Span(file="x.py", start_line=10, end_line=12)  # ok — range
    with pytest.raises(ValidationError):
        Span(file="x.py", start_line=10, end_line=9)


def test_patch_hunk_count_must_be_positive():
    with pytest.raises(ValidationError):
        Patch(file="a.py", diff="@@ -1 +1 @@\n-a\n+b\n", hunk_count=0)


# --- top-level re-exports ---------------------------------------------


def test_top_level_imports():
    assert af.SimpleFinding is SimpleFinding
    assert af.PatchFinding is PatchFinding
    assert af.NarrativeFinding is NarrativeFinding
    assert af.MultiSpanFinding is MultiSpanFinding
    assert af.Patch is Patch
    assert af.Span is Span
