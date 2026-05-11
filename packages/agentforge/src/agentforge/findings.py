"""Finding variants and helper value types (feat-008).

The `Finding` Protocol itself lives in `agentforge_core.contracts.finding`
(shipped under feat-001). This module ships the four built-in variants
plus the `Patch` and `Span` helpers two of them embed.

Variants are **frozen Pydantic v2 models** (per ADR-0014, deviating
from spec §4.2's `@dataclass` sketch). The external shape is the same;
the model framework gives us validation on construction, declarative
schema, and `model_dump` / `model_validate` round-trip — important
because findings cross persistence (`Claim.payload`), transport
(A2A / MCP / pipeline aggregation), and LLM-output (structured-output
emission) boundaries.

Each variant satisfies the `Finding` Protocol structurally — no
inheritance from the Protocol is required. The Protocol is
`runtime_checkable`, so `isinstance(x, Finding)` works.
"""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Patch(BaseModel):
    """A structured diff embedded inside a `PatchFinding`.

    Attributes:
        file: Path to the file the diff applies against, relative to
            repo root (e.g. `"src/foo.py"`).
        diff: Unified-diff text. Must be a complete, applyable hunk
            (or set of hunks against a single file).
        hunk_count: Number of `@@` headers in `diff`. Cached at
            construction; renderers may use it for summary stats.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    file: str = Field(min_length=1)
    diff: str = Field(min_length=1)
    hunk_count: int = Field(default=1, ge=1)


class Span(BaseModel):
    """A single source-range citation inside a `MultiSpanFinding`.

    Attributes:
        file: Path the span is in, relative to repo root.
        start_line: 1-indexed first line of the span.
        end_line: 1-indexed last line of the span (inclusive). Must
            be `>= start_line`.
        excerpt: The text on those lines (optional; useful for
            renderers that can't read the source file themselves,
            e.g. when findings are persisted and rendered later).
    """

    model_config = ConfigDict(frozen=True, strict=True)

    file: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    excerpt: str = ""

    @field_validator("end_line")
    @classmethod
    def _end_after_start(cls, end_line: int, info: Any) -> int:
        start = info.data.get("start_line")
        if start is not None and end_line < start:
            raise ValueError(f"end_line ({end_line}) must be >= start_line ({start})")
        return end_line


class _FindingBase(BaseModel):
    """Internal base — shared config + `to_dict` / `from_dict` plumbing.

    Not part of the public surface. Each variant subclasses this to
    inherit the round-trip helpers. Subclasses MUST declare the
    Protocol-required attributes (`severity`, `category`, `message`)
    themselves so `isinstance(x, Finding)` resolves correctly.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    def to_dict(self) -> dict[str, Any]:
        """JSON-compatible serialisation. Round-trips via `from_dict`."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct a typed variant from a `to_dict()` payload."""
        return cls.model_validate(data)


class SimpleFinding(_FindingBase):
    """The default variant — a severity-tagged issue or observation.

    Use for code-review-style output, lint hits, audit notes — anything
    that maps to "one finding = one location + one recommendation".
    """

    severity: str = Field(min_length=1)
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    recommendation: str = ""
    file: str = ""
    line: int | None = None
    rule_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class PatchFinding(_FindingBase):
    """Finding that ships a structured patch the consumer can apply.

    Use for refactor bots, codemod agents, and auto-fix suggestions.
    `confidence` is a model-supplied estimate in `[0, 1]`; downstream
    automation typically gates application on it.
    """

    severity: str = Field(min_length=1)
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    patch: Patch
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class NarrativeFinding(_FindingBase):
    """Long-form prose answer with citations.

    Use for docs-Q&A, research summaries, explanatory output. `body`
    is markdown; `references` is a flat list of pointer strings (free
    form — typical shapes are `"path:line"`, URLs, or section anchors).
    """

    severity: str = Field(min_length=1)
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    body: str = Field(min_length=1)
    references: list[str] = Field(default_factory=list)


class MultiSpanFinding(_FindingBase):
    """One logical issue manifested across multiple source locations.

    Use for cross-file findings like "hard-coded secret present in N
    files" or "this deprecated API is used in N places". `spans` lists
    every site; a renderer typically produces one block per span.
    """

    severity: str = Field(min_length=1)
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    spans: list[Span] = Field(min_length=1)
    recommendation: str = ""


__all__ = [
    "MultiSpanFinding",
    "NarrativeFinding",
    "Patch",
    "PatchFinding",
    "SimpleFinding",
    "Span",
]
