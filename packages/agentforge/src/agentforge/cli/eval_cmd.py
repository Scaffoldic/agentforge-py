"""`agentforge eval` — run an agent against JSONL fixtures (feat-017 chunk 5).

Each fixture line:

    {"task": "...", "expected": "...", "metadata": {...}}

The command builds the agent once, iterates fixtures, runs the agent
on each, aggregates per-evaluator scores, and threshold-checks the
mean. Output formats: rich (default), json, junit. Exit 5 on
threshold failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from xml.etree import (
    ElementTree as ET,  # nosec B405 — output only; never parses untrusted XML
)

from pydantic import ValidationError

from agentforge.cli._build import load_and_build
from agentforge.cli.run_cmd import (
    EXIT_CONFIG_INVALID,
    EXIT_GENERIC,
    EXIT_OK,
)

EXIT_THRESHOLD = 5


def register_eval_cmd(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = sub.add_parser(
        "eval",
        help="Run an agent against JSONL fixtures and apply evaluators.",
    )
    parser.add_argument("--fixtures", type=Path, required=True, help="Path to JSONL fixtures.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Minimum mean score across all evaluators. Exit 5 if below.",
    )
    parser.add_argument(
        "--output-format",
        choices=("rich", "json", "junit"),
        default="rich",
    )
    parser.add_argument("--path", type=Path, default=None)
    parser.add_argument("--env", default=None)
    parser.add_argument("--override", action="append", default=[])
    parser.set_defaults(_handler=_eval_handler)


def _eval_handler(args: argparse.Namespace) -> int:
    return asyncio.run(_dispatch(args))


async def _dispatch(args: argparse.Namespace) -> int:
    try:
        fixtures = _load_fixtures(args.fixtures)
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"agentforge eval: failed to read fixtures: {exc}\n")
        return EXIT_GENERIC

    try:
        agent = await load_and_build(
            path=args.path,
            env=args.env,
            overrides=list(args.override) or None,
        )
    except ValidationError as exc:
        sys.stderr.write(f"agentforge eval: config invalid:\n{exc}\n")
        return EXIT_CONFIG_INVALID

    results: list[dict[str, Any]] = []
    for fix in fixtures:
        run_result = await agent.run(fix["task"])
        results.append(
            {
                "task": fix["task"],
                "expected": fix.get("expected"),
                "output": run_result.output,
                "scores": [score.model_dump(mode="json") for score in run_result.eval_scores],
                "run_id": run_result.run_id,
            }
        )

    mean = _mean_score(results)
    fail = args.threshold is not None and mean < args.threshold

    _emit(results, mean, args.threshold, args.output_format, fail=fail)
    return EXIT_THRESHOLD if fail else EXIT_OK


def _load_fixtures(path: Path) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        fixtures.append(json.loads(stripped))
    return fixtures


def _mean_score(results: list[dict[str, Any]]) -> float:
    values: list[float] = []
    for r in results:
        for s in r["scores"]:
            score = s.get("score")
            if isinstance(score, int | float):
                values.append(float(score))
    return sum(values) / len(values) if values else 0.0


def _emit(
    results: list[dict[str, Any]],
    mean: float,
    threshold: float | None,
    fmt: str,
    *,
    fail: bool,
) -> None:
    if fmt == "json":
        print(
            json.dumps(
                {
                    "fixtures": len(results),
                    "mean_score": mean,
                    "threshold": threshold,
                    "passed": not fail,
                    "results": results,
                },
                indent=2,
            )
        )
        return
    if fmt == "junit":
        print(_to_junit(results, mean, fail=fail))
        return
    # Rich-or-plain summary.
    print(f"fixtures: {len(results)}")
    print(f"mean_score: {mean:.4f}")
    if threshold is not None:
        print(f"threshold: {threshold:.4f}  →  {'FAIL' if fail else 'PASS'}")


def _to_junit(results: list[dict[str, Any]], mean: float, *, fail: bool) -> str:
    suite = ET.Element(
        "testsuite",
        attrib={
            "name": "agentforge-eval",
            "tests": str(len(results)),
            "failures": "1" if fail else "0",
        },
    )
    for i, r in enumerate(results):
        case = ET.SubElement(
            suite,
            "testcase",
            attrib={"name": f"fixture[{i}]", "classname": "agentforge.eval"},
        )
        for score in r["scores"]:
            if score.get("score", 1.0) < 1.0:
                f = ET.SubElement(case, "failure", attrib={"type": "score"})
                f.text = json.dumps(score)
    if fail:
        f = ET.SubElement(
            suite,
            "system-err",
        )
        f.text = f"mean_score {mean:.4f} below threshold"
    return ET.tostring(suite, encoding="unicode")


__all__ = ["register_eval_cmd"]
