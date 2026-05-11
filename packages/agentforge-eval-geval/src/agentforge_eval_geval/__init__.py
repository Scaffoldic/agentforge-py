"""LLM-judge evaluators (G-Eval) for AgentForge — feat-006.

Public surface:
- `GEval` — the underlying engine, parameterised by a judge `LLMClient`
  and a rubric (dict or YAML file).
- Six named graders that wrap `GEval` with reference rubrics shipped
  inside the package: `Correctness`, `Faithfulness`, `Groundedness`,
  `Hallucination`, `Relevance`, `Helpfulness`.
"""

from __future__ import annotations

from agentforge_eval_geval.engine import GEval
from agentforge_eval_geval.graders import (
    Correctness,
    Faithfulness,
    Groundedness,
    Hallucination,
    Helpfulness,
    Relevance,
)

__all__ = [
    "Correctness",
    "Faithfulness",
    "GEval",
    "Groundedness",
    "Hallucination",
    "Helpfulness",
    "Relevance",
]
