"""Golden-set runner for agents (feat-016 chunk 4).

Runs an agent against a fixture file (JSONL) and compares the
output to a recorded golden. Mismatches surface as `GoldenMismatch`
exceptions so test runners (pytest etc) see them as test failures.

Fixture line shape::

    {
      "task": "What is the capital of France?",
      "expected": "Paris",          // exact match
      "metadata": {...}              // pass-through
    }

For looser matches, use:

- `expected: {"contains": "Paris"}` — substring assertion
- `expected: {"regex": "^Paris.*"}` — regex (re.search)
- `expected: {"any_of": ["Paris", "paris"]}` — case-insensitive
  membership

The runner is intentionally minimal — a structural-diff harness
deferred to follow-up sub-features that consume specific finding
shapes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentforge.agent import Agent


@dataclass(frozen=True)
class GoldenFixture:
    """A single fixture line loaded from a JSONL file."""

    task: str
    expected: str | dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GoldenResult:
    """The outcome of running an agent against one fixture."""

    fixture: GoldenFixture
    output: str | dict[str, Any]
    passed: bool
    detail: str | None = None


class GoldenMismatch(AssertionError):  # noqa: N818 — mirrors pytest's AssertionError shape
    """Raised when a fixture's expected value doesn't match the
    agent's output. Inherits AssertionError so pytest surfaces it
    naturally."""


class GoldenSetRunner:
    """Drive an agent through every fixture in a JSONL file."""

    def __init__(self, fixtures: list[GoldenFixture]) -> None:
        self._fixtures = list(fixtures)

    @classmethod
    def from_jsonl(cls, path: str | Path) -> GoldenSetRunner:
        """Load a `.jsonl` of fixtures."""
        raw = Path(path).read_text(encoding="utf-8").splitlines()
        fixtures: list[GoldenFixture] = []
        for line in raw:
            stripped = line.strip()
            if not stripped:
                continue
            obj = json.loads(stripped)
            fixtures.append(
                GoldenFixture(
                    task=obj["task"],
                    expected=obj.get("expected"),
                    metadata=obj.get("metadata", {}),
                )
            )
        return cls(fixtures)

    async def run(
        self,
        agent_factory: Callable[[], Agent | Awaitable[Agent]],
        *,
        mode: str = "aggregate",
    ) -> list[GoldenResult]:
        """Run every fixture; return one `GoldenResult` per fixture.

        `mode="aggregate"` (default) returns every result; the
        caller decides what to do with failures. `mode="fail-fast"`
        raises `GoldenMismatch` on the first failure.
        """
        results: list[GoldenResult] = []
        for fixture in self._fixtures:
            built = agent_factory()
            agent = await built if hasattr(built, "__await__") else built
            run_result = await agent.run(fixture.task)
            passed, detail = _check(fixture.expected, run_result.output)
            results.append(
                GoldenResult(
                    fixture=fixture,
                    output=run_result.output,
                    passed=passed,
                    detail=detail,
                )
            )
            if not passed and mode == "fail-fast":
                msg = (
                    f"golden mismatch on task={fixture.task!r}: {detail}. "
                    f"Got: {run_result.output!r}"
                )
                raise GoldenMismatch(msg)
        return results


def _check(
    expected: str | dict[str, Any] | None,
    actual: str | dict[str, Any],
) -> tuple[bool, str | None]:
    """Compare `expected` against `actual`; return (passed, detail)."""
    if expected is None:
        return True, None
    actual_str = actual if isinstance(actual, str) else json.dumps(actual, sort_keys=True)
    if isinstance(expected, str):
        return (expected == actual_str, None if expected == actual_str else "exact mismatch")
    if isinstance(expected, dict):
        if "contains" in expected:
            sub = expected["contains"]
            return (sub in actual_str, None if sub in actual_str else f"missing substring {sub!r}")
        if "regex" in expected:
            pat = re.compile(expected["regex"])
            matched = pat.search(actual_str) is not None
            return (matched, None if matched else f"regex {expected['regex']!r} did not match")
        if "any_of" in expected:
            choices = [s.lower() for s in expected["any_of"]]
            ok = actual_str.lower() in choices
            return (ok, None if ok else f"value not in any_of={choices}")
    msg = f"unsupported expected shape: {expected!r}"
    raise ValueError(msg)


__all__ = [
    "GoldenFixture",
    "GoldenMismatch",
    "GoldenResult",
    "GoldenSetRunner",
]
