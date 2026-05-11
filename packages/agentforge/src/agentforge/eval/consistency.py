"""`Consistency` — deterministic grader for "same input → same output".

Re-runs the task N times via a caller-supplied async function and
scores the agreement of the N outputs against the original output.
The re-run function is the seam — for unit tests it can be a
scripted-response function; in production it typically wraps another
`Agent.run(task)` call.

The grader declares `cost_estimate_usd = 0.0` against the evaluator
budget gate (it doesn't bill itself), but the re-run function calls
the LLM and bills against the run's `BudgetPolicy` like any other
agent call. The caller is responsible for ensuring the runner
respects the same budget if they want a unified cost cap.

Score = fraction of re-runs whose output matches the original. The
match function defaults to strict equality; pass a custom
`matcher` for fuzzy comparison (cosine similarity, normalised
string compare, etc.).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from agentforge_core.contracts.evaluator import EvalResult, Evaluator

Runner = Callable[[str], Awaitable[Any]]
"""Async function that re-executes the task and returns the new output."""

Matcher = Callable[[Any, Any], bool]
"""Equality check between the original output and one re-run output."""


class Consistency(Evaluator):
    """Score the fraction of N re-runs that match the original output."""

    name: ClassVar[str] = "consistency"
    # The grader itself does not call an LLM; re-runs bill against the
    # outer run's BudgetPolicy via the caller-supplied runner. The
    # evaluator gate treats this as $0 so it isn't skipped even on a
    # tight budget; budget exhaustion will manifest as the runner
    # itself raising BudgetExceeded.
    cost_estimate_usd: ClassVar[float] = 0.0

    def __init__(
        self,
        *,
        runner: Runner,
        n_samples: int = 3,
        matcher: Matcher | None = None,
    ) -> None:
        if n_samples < 1:
            raise ValueError(f"n_samples must be >= 1; got {n_samples}")
        self._runner = runner
        self._n = n_samples
        self._matcher: Matcher = matcher if matcher is not None else _strict_eq

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        task = context.get("task")
        if not isinstance(task, str):
            return EvalResult(
                evaluator=self.name,
                score=0.0,
                label="fail",
                reasoning="context['task'] missing or not a string",
            )
        original = finding.output if hasattr(finding, "output") else finding

        agreements = 0
        rerun_outputs: list[Any] = []
        for i in range(self._n):
            try:
                replay = await self._runner(task)
            except Exception as exc:
                return EvalResult(
                    evaluator=self.name,
                    score=0.0,
                    label="fail",
                    reasoning=f"re-run {i + 1}/{self._n} raised {type(exc).__name__}: {exc}",
                    raw={"rerun_outputs": rerun_outputs},
                )
            rerun_outputs.append(replay)
            if self._matcher(original, replay):
                agreements += 1

        score = agreements / self._n
        label = "pass" if agreements == self._n else "warn" if agreements > 0 else "fail"
        return EvalResult(
            evaluator=self.name,
            score=score,
            label=label,
            reasoning=f"{agreements}/{self._n} re-runs matched the original",
            raw={
                "n_samples": self._n,
                "agreements": agreements,
                "original": original,
                "rerun_outputs": rerun_outputs,
            },
        )


def _strict_eq(a: Any, b: Any) -> bool:
    return bool(a == b)


__all__ = ["Consistency", "Matcher", "Runner"]
