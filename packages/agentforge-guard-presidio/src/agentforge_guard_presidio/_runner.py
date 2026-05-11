"""Internal Presidio runner protocol (feat-018).

`PresidioOutput` consumes a `PresidioRunner` so tests inject a
fake without requiring `presidio-analyzer` to be installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PresidioFinding:
    """Single PII match: entity type, span, confidence."""

    entity_type: str
    start: int
    end: int
    score: float


class PresidioRunner(Protocol):
    """Slice of `presidio_analyzer.AnalyzerEngine` + anonymizer we
    depend on.

    `analyze(text, entities, score_threshold)` returns the matches
    above the threshold. `anonymize(text, findings)` returns the
    anonymised text with each match replaced by `<KIND>`.
    """

    async def analyze(
        self,
        text: str,
        entities: list[str],
        score_threshold: float,
    ) -> list[PresidioFinding]: ...

    async def anonymize(
        self,
        text: str,
        findings: list[PresidioFinding],
    ) -> str: ...


class _RealPresidioRunner:
    """Production runner — lazy-imports `presidio_analyzer` and
    `presidio_anonymizer`. Surfaces a clear `ModuleError` with pip
    remediation if either isn't installed."""

    def __init__(self) -> None:
        self._analyzer: object | None = None
        self._anonymizer: object | None = None

    async def analyze(
        self,
        text: str,
        entities: list[str],
        score_threshold: float,
    ) -> list[PresidioFinding]:
        analyzer = self._get_analyzer()
        results = analyzer.analyze(text=text, entities=entities, language="en")  # type: ignore[attr-defined]
        return [
            PresidioFinding(
                entity_type=r.entity_type,
                start=r.start,
                end=r.end,
                score=float(r.score),
            )
            for r in results
            if float(r.score) >= score_threshold
        ]

    async def anonymize(
        self,
        text: str,
        findings: list[PresidioFinding],
    ) -> str:
        # Sort by start descending so replacements don't shift
        # subsequent indices.
        out = text
        for f in sorted(findings, key=lambda x: x.start, reverse=True):
            out = out[: f.start] + f"<{f.entity_type}>" + out[f.end :]
        return out

    def _get_analyzer(self) -> object:
        if self._analyzer is not None:
            return self._analyzer
        try:
            from presidio_analyzer import AnalyzerEngine  # noqa: PLC0415
        except ImportError as exc:
            from agentforge_core.production.exceptions import ModuleError  # noqa: PLC0415

            msg = (
                "presidio-analyzer is not installed. Install via "
                "`pip install presidio-analyzer presidio-anonymizer` to "
                "use `PresidioOutput`."
            )
            raise ModuleError(msg) from exc
        self._analyzer = AnalyzerEngine()
        return self._analyzer


__all__ = ["PresidioFinding", "PresidioRunner"]
