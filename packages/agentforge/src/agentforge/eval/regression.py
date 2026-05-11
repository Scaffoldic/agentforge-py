"""`RegressionVsBaseline` — deterministic grader against a locked baseline.

The baseline file is a JSONL (one JSON object per line) where each
entry is keyed by `task`:

    {"task": "Summarise PR #42", "expected": "PR #42 adds X..."}
    {"task": "List failing tests",  "expected": ["test_a", "test_b"]}

At construction the file is loaded into a `{task: expected_output}`
map. For each `evaluate` call the grader picks the baseline entry
matching `context["task"]` and compares `finding.output` against it.

Two modes pick the comparison:
  - `mode="exact"` (default) — `output == expected`. Score 1.0 or 0.0.
  - `mode="structural"` — output and expected are both dicts;
    score = fraction of matching keys (case-sensitive on both keys
    and values).

Result labels:
  - `"improved"` — exact-match in exact mode; perfect structural match.
  - `"regressed"` — mismatch in either mode.
  - `"no_baseline"` — no entry in the baseline file matches the task.
    Score is NaN; the evaluator does not claim regression in this case.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, ClassVar, Literal

from agentforge_core.contracts.evaluator import EvalResult, Evaluator

_Mode = Literal["exact", "structural"]


class RegressionVsBaseline(Evaluator):
    """Score the current run vs a locked baseline file."""

    name: ClassVar[str] = "regression_vs_baseline"
    cost_estimate_usd: ClassVar[float] = 0.0

    def __init__(
        self,
        *,
        baseline_path: str | Path,
        mode: _Mode = "exact",
    ) -> None:
        if mode not in ("exact", "structural"):
            raise ValueError(f"mode must be 'exact' or 'structural'; got {mode!r}")
        self._mode = mode
        self._baselines: dict[str, Any] = self._load(Path(baseline_path))

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"baseline file not found: {path}")
        out: dict[str, Any] = {}
        with path.open(encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"baseline {path}:{lineno} is not valid JSON: {exc.msg}"
                    ) from exc
                if not isinstance(entry, dict) or "task" not in entry or "expected" not in entry:
                    raise ValueError(
                        f"baseline {path}:{lineno} must have 'task' and 'expected' keys"
                    )
                out[entry["task"]] = entry["expected"]
        if not out:
            raise ValueError(f"baseline file {path} is empty")
        return out

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        task = context.get("task")
        if not isinstance(task, str) or task not in self._baselines:
            return EvalResult(
                evaluator=self.name,
                score=math.nan,
                label="no_baseline",
                reasoning=f"no baseline entry for task {task!r}",
            )

        expected = self._baselines[task]
        output = finding.output if hasattr(finding, "output") else finding

        if self._mode == "exact":
            matches = output == expected
            return EvalResult(
                evaluator=self.name,
                score=1.0 if matches else 0.0,
                label="improved" if matches else "regressed",
                reasoning="exact match" if matches else "output differs from baseline",
                raw={"expected": expected, "actual": output},
            )

        # Structural mode.
        if not isinstance(expected, dict) or not isinstance(output, dict):
            return EvalResult(
                evaluator=self.name,
                score=0.0,
                label="regressed",
                reasoning=(
                    f"structural mode requires dict output and dict baseline; "
                    f"got output={type(output).__name__}, expected={type(expected).__name__}"
                ),
            )
        return self._compare_structural(output, expected)

    def _compare_structural(self, output: dict[str, Any], expected: dict[str, Any]) -> EvalResult:
        all_keys = expected.keys() | output.keys()
        matching = [
            k for k in all_keys if k in expected and k in output and output[k] == expected[k]
        ]
        missing = sorted(k for k in expected if k not in output)
        extra = sorted(k for k in output if k not in expected)
        mismatched = sorted(k for k in expected if k in output and output[k] != expected[k])
        score = len(matching) / len(all_keys) if all_keys else 1.0
        label = "improved" if score == 1.0 else "regressed"
        return EvalResult(
            evaluator=self.name,
            score=score,
            label=label,
            reasoning=(
                f"structural match {len(matching)}/{len(all_keys)} keys "
                f"(missing={missing}, extra={extra}, mismatched={mismatched})"
            ),
            raw={
                "matched_keys": sorted(matching),
                "missing_keys": missing,
                "extra_keys": extra,
                "mismatched_keys": mismatched,
            },
        )


__all__ = ["RegressionVsBaseline"]
