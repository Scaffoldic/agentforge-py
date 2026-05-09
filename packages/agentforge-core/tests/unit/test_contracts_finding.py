"""Unit tests for the `Finding` Protocol."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from agentforge_core.contracts.finding import Finding


@dataclass
class _SimpleFinding:
    severity: str
    category: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def test_dataclass_with_required_attrs_satisfies_protocol() -> None:
    finding = _SimpleFinding(severity="warning", category="style", message="x")
    assert isinstance(finding, Finding)


def test_object_missing_severity_does_not_satisfy_protocol() -> None:
    class _Half:
        category = "x"
        message = "y"

        def to_dict(self) -> dict[str, Any]:
            return {}

    assert not isinstance(_Half(), Finding)


def test_object_missing_to_dict_does_not_satisfy_protocol() -> None:
    @dataclass
    class _NoDict:
        severity: str
        category: str
        message: str

    assert not isinstance(_NoDict("a", "b", "c"), Finding)


def test_arbitrary_class_with_protocol_shape_qualifies() -> None:
    """Domain-specific variants satisfy the Protocol structurally —
    no inheritance required (per feat-008 / ADR-0012)."""

    class _CoverageFinding:
        severity: str = "info"
        category: str = "coverage"
        message: str = "Module foo has 80% coverage"

        def to_dict(self) -> dict[str, Any]:
            return {
                "severity": self.severity,
                "category": self.category,
                "message": self.message,
            }

    assert isinstance(_CoverageFinding(), Finding)
