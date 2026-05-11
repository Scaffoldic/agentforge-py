"""`Coverage` — deterministic grader for "what fraction of expected items did the agent find?"

The reference set is supplied at construction; the grader extracts the
agent's items from `RunResult.output` (string match by default; callable
override for structural extraction) and computes
`score = |intersection| / |reference|` clamped to `[0, 1]`.

Use for code-review agents (did the agent flag every known issue?),
RAG agents (did the answer cite every required source?), and any
task where ground truth is "should mention exactly these things".
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, ClassVar

from agentforge_core.contracts.evaluator import EvalResult, Evaluator


class Coverage(Evaluator):
    """Fraction of expected items present in the agent's output.

    Construction:

        Coverage(reference={"sql injection", "xss", "csrf"})

        # Or with a custom extractor (e.g. structured output):
        Coverage(
            reference={"item-1", "item-2"},
            extractor=lambda out: set(out["found"]),
        )

    By default, items are matched against the output by case-
    insensitive substring containment. Pass `extractor` for structural
    matching (e.g. read a list from `output["findings"]`).
    """

    name: ClassVar[str] = "coverage"
    cost_estimate_usd: ClassVar[float] = 0.0

    def __init__(
        self,
        *,
        reference: Iterable[str],
        extractor: Callable[[str | dict[str, Any]], set[str]] | None = None,
    ) -> None:
        ref = {r for r in reference if r}
        if not ref:
            raise ValueError("Coverage requires a non-empty reference set")
        self._reference: frozenset[str] = frozenset(ref)
        self._extractor = extractor

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        del context
        output = finding.output if hasattr(finding, "output") else finding
        found_normalised, raw_found = self._find_present(output)

        matched = sorted(found_normalised)
        missing = sorted(r for r in self._reference if r.lower() not in found_normalised)
        score = (len(self._reference) - len(missing)) / len(self._reference)
        label = "pass" if not missing else "warn" if matched else "fail"

        return EvalResult(
            evaluator=self.name,
            score=score,
            label=label,
            reasoning=(
                f"matched {len(matched)}/{len(self._reference)}; missing={missing}"
                if missing
                else f"matched {len(matched)}/{len(self._reference)}; all present"
            ),
            raw={
                "matched": matched,
                "missing": missing,
                "extracted": sorted(raw_found),
            },
        )

    def _find_present(self, output: Any) -> tuple[set[str], set[str]]:
        """Return `(matched_normalised, raw_extracted)`.

        `matched_normalised` is the subset of `self._reference`, lower-
        cased, that the output contains. `raw_extracted` is whatever the
        extractor produced (for diagnostics in `raw`).
        """
        if self._extractor is not None:
            raw_found = self._extractor(output)
            found_lower = {item.lower() for item in raw_found}
            matched = {r.lower() for r in self._reference if r.lower() in found_lower}
            return matched, raw_found

        # Default substring match against a single text blob.
        text = output if isinstance(output, str) else str(output)
        text_lower = text.lower()
        matched = {r.lower() for r in self._reference if r.lower() in text_lower}
        return matched, {text}


__all__ = ["Coverage"]
