"""`GEval` — generic LLM-judge engine driven by a rubric.

The rubric is a dict (or YAML file) declaring `criteria`, `scoring`,
and optional `examples`. The engine renders a system + user prompt
that asks the judge to return a JSON object with `score` (float in
`[0, 1]`) and `reasoning` (string). Output is parsed defensively —
malformed responses degrade to a `fail` `EvalResult` with the raw
text in `raw`.

The judge is any `LLMClient`. To keep costs bounded, this engine
declares a per-call `cost_estimate_usd` (default 0.01); the agent's
evaluator gate uses it for skip decisions. Actual cost from the
judge call is added to `BudgetPolicy.spent_usd` via the standard
`BudgetPolicy.commit(cost)` after the call completes (when a budget
is supplied via the evaluator context).
"""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any, ClassVar

import yaml
from agentforge_core.contracts.evaluator import EvalResult, Evaluator
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.values.messages import Message

_PASS_THRESHOLD = 0.5
"""Score >= this value is labelled `"pass"`; below is `"fail"`."""


class GEval(Evaluator):
    """LLM-judge grader. Subclass or use directly with a custom rubric."""

    name: ClassVar[str] = "geval"
    cost_estimate_usd: ClassVar[float] = 0.01

    def __init__(
        self,
        *,
        judge: LLMClient,
        rubric: dict[str, Any],
        name: str | None = None,
        cost_estimate_usd: float | None = None,
    ) -> None:
        if not isinstance(rubric, dict):
            raise TypeError("rubric must be a dict")
        criteria = rubric.get("criteria")
        scoring = rubric.get("scoring")
        if not isinstance(criteria, str) or not criteria.strip():
            raise ValueError("rubric must include a non-empty 'criteria' string")
        if not isinstance(scoring, str) or not scoring.strip():
            raise ValueError("rubric must include a non-empty 'scoring' string")
        self._judge = judge
        self._rubric = dict(rubric)
        # Per-instance name override shadows the ClassVar so subclasses
        # / callers can rename without subclassing.
        if name is not None:
            self.name = name  # type: ignore[misc]
        if cost_estimate_usd is not None:
            # Per-instance override so callers can declare a cheaper rubric.
            self.cost_estimate_usd = cost_estimate_usd  # type: ignore[misc]

    @classmethod
    def from_rubric_file(
        cls,
        path: str | Path,
        *,
        judge: LLMClient,
        name: str | None = None,
    ) -> GEval:
        """Load a rubric YAML and construct a GEval grader."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"rubric file not found: {path}")
        with path.open(encoding="utf-8") as fh:
            rubric = yaml.safe_load(fh)
        if not isinstance(rubric, dict):
            raise TypeError(f"rubric file {path} must contain a YAML mapping")
        return cls(judge=judge, rubric=rubric, name=name or path.stem)

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        output = finding.output if hasattr(finding, "output") else finding
        task = context.get("task", "")
        budget = context.get("budget")

        system, user = self._build_prompt(output=output, task=task, context=context)
        messages = [Message(role="user", content=user)]
        try:
            response = await self._judge.call(system=system, messages=messages)
        except Exception as exc:
            return EvalResult(
                evaluator=self.name,
                score=0.0,
                label="fail",
                reasoning=f"judge call raised {type(exc).__name__}: {exc}",
            )

        if isinstance(budget, BudgetPolicy) and response.cost_usd > 0:
            # Commit failure (e.g. would push over cap) shouldn't void
            # the result — the score is still informative.
            with contextlib.suppress(Exception):
                budget.commit(response.cost_usd)

        score, reasoning = self._parse_response(response.content)
        return EvalResult(
            evaluator=self.name,
            score=score,
            label="pass" if score >= _PASS_THRESHOLD else "fail",
            reasoning=reasoning,
            raw={
                "judge_cost_usd": response.cost_usd,
                "judge_tokens_in": response.usage.input_tokens,
                "judge_tokens_out": response.usage.output_tokens,
                "raw_text": response.content,
            },
        )

    def _build_prompt(self, *, output: Any, task: str, context: dict[str, Any]) -> tuple[str, str]:
        """Render the system + user prompts from the rubric.

        Available rubric fields:
          - `criteria`: what to judge
          - `scoring`: how to score
          - `examples`: optional list of {output, score, reasoning}
          - `inputs`: optional list of context keys to inject
            (e.g. ["expected", "retrieved_docs"]). The values are
            pulled from the eval `context` dict and rendered.
        """
        criteria = self._rubric["criteria"]
        scoring = self._rubric["scoring"]

        system = (
            "You are an expert evaluator. Score the provided output against the rubric below.\n"
            f"Criteria: {criteria}\n"
            f"Scoring: {scoring}\n"
            "Respond ONLY with a JSON object: "
            '{"score": <float 0.0-1.0>, "reasoning": "<one-sentence explanation>"}.'
        )

        parts = [f"Task: {task}", f"Output:\n{output}"]
        inputs = self._rubric.get("inputs") or []
        for key in inputs:
            value = context.get(key)
            if value is not None:
                parts.append(f"{key}:\n{value}")
        examples = self._rubric.get("examples") or []
        if examples:
            parts.append("Examples:")
            parts.extend(
                f"  - output: {ex.get('output')!r}\n"
                f"    score: {ex.get('score')}\n"
                f"    reasoning: {ex.get('reasoning')}"
                for ex in examples
            )
        return system, "\n\n".join(parts)

    @staticmethod
    def _parse_response(text: str) -> tuple[float, str]:
        """Extract `score` + `reasoning` from the judge's JSON response.

        Defensive: if the judge returned text wrapped in markdown
        fences or with chatter around the JSON, we extract the first
        `{...}` block. If parsing fails entirely, return `(0.0,
        "judge returned unparseable response: ...")`.
        """
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match is None:
            return 0.0, f"judge returned no JSON: {text[:200]}"
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            return 0.0, f"judge returned unparseable JSON: {exc.msg}"

        score = payload.get("score")
        if not isinstance(score, (int, float)):
            return 0.0, f"judge response missing numeric 'score': {payload}"
        score = max(0.0, min(1.0, float(score)))
        reasoning = payload.get("reasoning")
        if not isinstance(reasoning, str):
            reasoning = ""
        return score, reasoning


__all__ = ["GEval"]
