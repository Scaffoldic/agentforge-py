"""Six named LLM-judge graders backed by `GEval`.

Each grader loads its rubric from the package-shipped YAML files in
`rubrics/`. The judge `LLMClient` is required at construction;
optional kwargs let callers point the rubric at specific context
keys (e.g. `ground_truth_field`, `sources_field`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import yaml
from agentforge_core.contracts.llm import LLMClient

from agentforge_eval_geval.engine import GEval

_RUBRICS_DIR = Path(__file__).parent / "rubrics"


def _load_rubric(name: str) -> dict[str, Any]:
    path = _RUBRICS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"shipped rubric {name!r} not found at {path}")
    with path.open(encoding="utf-8") as fh:
        rubric = yaml.safe_load(fh)
    if not isinstance(rubric, dict):
        raise TypeError(f"shipped rubric {path} is malformed")
    return rubric


class _NamedGEval(GEval):
    """Internal base — subclasses pin the rubric name."""

    rubric_name: ClassVar[str]

    def __init__(self, *, judge: LLMClient, **rubric_overrides: Any) -> None:
        rubric = _load_rubric(self.rubric_name)
        # Allow callers to override the rubric's `inputs` (which
        # context keys to pull) — common for `Correctness`
        # (ground_truth_field) and `Faithfulness` (sources_field).
        if rubric_overrides:
            inputs = list(rubric.get("inputs") or [])
            for value in rubric_overrides.values():
                if isinstance(value, str) and value not in inputs:
                    inputs.append(value)
            rubric["inputs"] = inputs
        super().__init__(judge=judge, rubric=rubric, name=self.rubric_name)


class Correctness(_NamedGEval):
    rubric_name: ClassVar[str] = "correctness"

    def __init__(
        self,
        *,
        judge: LLMClient,
        ground_truth_field: str = "expected",
    ) -> None:
        super().__init__(judge=judge, ground_truth_field=ground_truth_field)


class Faithfulness(_NamedGEval):
    rubric_name: ClassVar[str] = "faithfulness"

    def __init__(
        self,
        *,
        judge: LLMClient,
        sources_field: str = "retrieved_docs",
    ) -> None:
        super().__init__(judge=judge, sources_field=sources_field)


class Groundedness(_NamedGEval):
    rubric_name: ClassVar[str] = "groundedness"

    def __init__(
        self,
        *,
        judge: LLMClient,
        sources_field: str = "retrieved_docs",
    ) -> None:
        super().__init__(judge=judge, sources_field=sources_field)


class Hallucination(_NamedGEval):
    rubric_name: ClassVar[str] = "hallucination"

    def __init__(
        self,
        *,
        judge: LLMClient,
        sources_field: str = "retrieved_docs",
    ) -> None:
        super().__init__(judge=judge, sources_field=sources_field)


class Relevance(_NamedGEval):
    rubric_name: ClassVar[str] = "relevance"

    def __init__(self, *, judge: LLMClient) -> None:
        super().__init__(judge=judge)


class Helpfulness(_NamedGEval):
    rubric_name: ClassVar[str] = "helpfulness"

    def __init__(self, *, judge: LLMClient) -> None:
        super().__init__(judge=judge)


__all__ = [
    "Correctness",
    "Faithfulness",
    "Groundedness",
    "Hallucination",
    "Helpfulness",
    "Relevance",
]
