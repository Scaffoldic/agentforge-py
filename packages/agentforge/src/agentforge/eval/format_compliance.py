"""`FormatCompliance` — deterministic grader for output shape.

Three modes pick the constraint applied to `RunResult.output`:
  - `regex=<pattern>` — output (str) must match the pattern.
  - `pydantic_model=<BaseModel subclass>` — output validates against
    the model. Accepts dict output directly or a string that
    parses as JSON.
  - `json_parseable=True` — output (str) must parse as JSON. No
    schema enforcement.

Exactly one mode must be set at construction. Future modes (Lark
grammars, ANTLR, JSON Schema via the `jsonschema` dep) can land in
follow-ups without breaking the constructor.
"""

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from agentforge_core.contracts.evaluator import EvalResult, Evaluator
from pydantic import BaseModel, ValidationError


class FormatCompliance(Evaluator):
    """Score = 1.0 (passes) or 0.0 (fails). Label is `"pass"` / `"fail"`."""

    name: ClassVar[str] = "format_compliance"
    cost_estimate_usd: ClassVar[float] = 0.0

    def __init__(
        self,
        *,
        regex: str | None = None,
        pydantic_model: type[BaseModel] | None = None,
        json_parseable: bool = False,
    ) -> None:
        modes_set = sum(
            1 for x in (regex is not None, pydantic_model is not None, json_parseable) if x
        )
        if modes_set != 1:
            raise ValueError(
                "FormatCompliance requires exactly one of regex=, pydantic_model=, json_parseable="
            )
        self._regex = re.compile(regex) if regex is not None else None
        self._model = pydantic_model
        self._json_parseable = json_parseable

    async def evaluate(self, finding: Any, context: dict[str, Any]) -> EvalResult:
        del context
        output = finding.output if hasattr(finding, "output") else finding
        if self._regex is not None:
            return self._check_regex(output)
        if self._model is not None:
            return self._check_model(output)
        return self._check_json(output)

    def _check_regex(self, output: Any) -> EvalResult:
        assert self._regex is not None
        if not isinstance(output, str):
            return _fail(f"regex mode requires string output; got {type(output).__name__}")
        if self._regex.fullmatch(output):
            return _pass(f"output matched regex {self._regex.pattern!r}")
        return _fail(f"output did not match regex {self._regex.pattern!r}")

    def _check_model(self, output: Any) -> EvalResult:
        assert self._model is not None
        candidate: Any
        if isinstance(output, dict):
            candidate = output
        elif isinstance(output, str):
            try:
                candidate = json.loads(output)
            except json.JSONDecodeError as exc:
                return _fail(f"output is not JSON-parseable: {exc.msg}")
        else:
            return _fail(
                f"pydantic_model mode requires dict or JSON string; got {type(output).__name__}"
            )
        try:
            self._model.model_validate(candidate)
        except ValidationError as exc:
            return _fail(f"validation failed: {exc.errors(include_url=False)}")
        return _pass(f"output validates against {self._model.__name__}")

    def _check_json(self, output: Any) -> EvalResult:
        if isinstance(output, dict):
            return _pass("output is already a dict (JSON-compatible)")
        if not isinstance(output, str):
            return _fail(f"json_parseable mode requires str or dict; got {type(output).__name__}")
        try:
            json.loads(output)
        except json.JSONDecodeError as exc:
            return _fail(f"output is not JSON-parseable: {exc.msg}")
        return _pass("output parses as JSON")


def _pass(reasoning: str) -> EvalResult:
    return EvalResult(evaluator=FormatCompliance.name, score=1.0, label="pass", reasoning=reasoning)


def _fail(reasoning: str) -> EvalResult:
    return EvalResult(evaluator=FormatCompliance.name, score=0.0, label="fail", reasoning=reasoning)


__all__ = ["FormatCompliance"]
