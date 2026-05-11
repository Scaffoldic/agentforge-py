"""Deterministic evaluators shipped in `agentforge` (feat-006).

Zero-cost graders that don't call an LLM — safe to run on every
output. LLM-judge graders ship separately in `agentforge-eval-geval`.

Each grader is constructible directly (`Coverage(reference={...})`),
or addressable by name through the resolver (`"coverage"` etc.) when
the runtime is asked to look up a grader by string.
"""

from __future__ import annotations

from agentforge.eval.coverage import Coverage
from agentforge.eval.format_compliance import FormatCompliance

__all__ = ["Coverage", "FormatCompliance"]
