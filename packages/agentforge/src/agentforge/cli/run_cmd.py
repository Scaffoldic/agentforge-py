"""`agentforge run` — invoke an Agent against a task (feat-017 chunk 4).

Configurable from the command line:

    agentforge run "Review this PR"
    agentforge run --task-file ./task.txt
    agentforge run --override agent.budget.usd=10 "..."
    agentforge run --output-format json "..."
    agentforge run --replay 01HX...  --to-step 5
    agentforge run --record "..."      # writes step claims to memory

Exit codes (locked in feat-017 §4):

    0  success
    1  generic error
    2  config invalid
    3  budget exceeded
    4  guardrail tripped
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from agentforge_core.production.exceptions import (
    BudgetExceeded,
    GuardrailViolation,
    ModuleError,
)
from pydantic import ValidationError

from agentforge.agent import Agent
from agentforge.cli._build import build_agent_from_config, build_memory_from_config
from agentforge.replay import ReplayLLMClient, load_pipeline_result

EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_CONFIG_INVALID = 2
EXIT_BUDGET = 3
EXIT_GUARDRAIL = 4


def register_run_cmd(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = sub.add_parser(
        "run",
        help="Run an agent against a task.",
        description="Run an agent against a task and print its output.",
    )
    parser.add_argument("task", nargs="?", default=None, help="Task text to run.")
    parser.add_argument(
        "--task-file",
        type=Path,
        default=None,
        help="Read the task body from a file (alternative to positional).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Path to agentforge.yaml (defaults to ./agentforge.yaml or $AGENTFORGE_CONFIG).",
    )
    parser.add_argument(
        "--env",
        default=None,
        help="Override AGENTFORGE_ENV for this run (selects agentforge.<env>.yaml).",
    )
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Dotted-path config override (repeatable), e.g. agent.budget.usd=5.",
    )
    parser.add_argument(
        "--output-format",
        choices=("rich", "json", "plain"),
        default=None,
        help="How to print the result. Default: rich if stdout is a TTY else plain.",
    )
    parser.add_argument(
        "--replay",
        default=None,
        metavar="RUN_ID",
        help="Replay a previously recorded run instead of calling the LLM.",
    )
    parser.add_argument(
        "--to-step",
        type=int,
        default=None,
        help="Stop replay after this many emitted steps (debug aid).",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Persist this run's steps + result to the configured memory store.",
    )
    parser.set_defaults(_handler=_run_handler)


def _run_handler(args: argparse.Namespace) -> int:
    return asyncio.run(_dispatch(args))


async def _dispatch(args: argparse.Namespace) -> int:
    task = _resolve_task(args)
    if task is None:
        sys.stderr.write("agentforge run: must provide a task or --task-file.\n")
        return EXIT_GENERIC

    config_or_code = _load_config_or_exit(args)
    if isinstance(config_or_code, int):
        return config_or_code

    try:
        agent, replay_pipeline = await _build_for_run(args, config_or_code)
    except ModuleError as exc:
        sys.stderr.write(f"agentforge run: failed to construct agent: {exc}\n")
        return EXIT_GENERIC

    return await _run_and_emit(agent, task, args.output_format, replay_pipeline=replay_pipeline)


def _load_config_or_exit(args: argparse.Namespace) -> Any:
    """Load config; return the config object or an exit code int."""
    from agentforge_core.config.loader import load_config  # noqa: PLC0415

    try:
        return load_config(args.path, env=args.env, overrides=list(args.override) or None)
    except ValidationError as exc:
        sys.stderr.write(f"agentforge run: config invalid:\n{exc}\n")
        return EXIT_CONFIG_INVALID
    except ModuleError as exc:
        sys.stderr.write(f"agentforge run: {exc}\n")
        return EXIT_CONFIG_INVALID


async def _run_and_emit(
    agent: Agent,
    task: str,
    output_format: str | None,
    *,
    replay_pipeline: Any | None = None,
) -> int:
    try:
        result = await agent.run(task, replay_pipeline=replay_pipeline)
    except BudgetExceeded as exc:
        sys.stderr.write(f"agentforge run: budget exceeded: {exc}\n")
        return EXIT_BUDGET
    except GuardrailViolation as exc:
        sys.stderr.write(f"agentforge run: guardrail tripped: {exc}\n")
        return EXIT_GUARDRAIL
    except ModuleError as exc:
        sys.stderr.write(f"agentforge run: {exc}\n")
        return EXIT_GENERIC
    _emit(result, output_format)
    return EXIT_OK


async def _build_for_run(args: argparse.Namespace, config: Any) -> tuple[Agent, Any | None]:
    """Wire an Agent, optionally substituting the LLM with a replay client.

    Returns ``(agent, replay_pipeline)`` — the second tuple item is a
    previously recorded `PipelineResult` (or ``None``) that the run
    handler threads into `Agent.run(replay_pipeline=...)` so a
    side-effect-bearing pipeline doesn't re-execute on replay.
    """
    if args.replay is not None:
        memory = build_memory_from_config(config)
        if memory is None:
            msg = "--replay requires modules.memory to be configured."
            raise ModuleError(msg)
        replay_llm = await ReplayLLMClient.from_recording(memory, args.replay)
        replay_pipeline = await load_pipeline_result(memory, args.replay)
        return Agent(model=replay_llm, memory=memory), replay_pipeline
    return await build_agent_from_config(config, enable_recording=args.record), None


def _resolve_task(args: argparse.Namespace) -> str | None:
    if args.task is not None and args.task_file is not None:
        msg = "agentforge run: pass either positional task or --task-file, not both.\n"
        sys.stderr.write(msg)
        return None
    if args.task is not None:
        return str(args.task)
    if args.task_file is not None:
        return Path(args.task_file).read_text(encoding="utf-8").strip()
    return None


def _emit(result: Any, output_format: str | None) -> None:
    fmt = output_format or ("rich" if sys.stdout.isatty() else "plain")
    if fmt == "json":
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    if fmt == "rich":
        _print_rich(result)
        return
    # Plain — just the output.
    output = result.output
    if isinstance(output, dict):
        print(json.dumps(output))
    else:
        print(output)


def _print_rich(result: Any) -> None:
    try:
        from rich.console import Console  # noqa: PLC0415
        from rich.table import Table  # noqa: PLC0415
    except ImportError:
        # Rich not installed — fall back to plain.
        _emit(result, "plain")
        return
    console = Console()
    table = Table(title="Run summary", show_header=True)
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("run_id", result.run_id)
    table.add_row("finish_reason", str(result.finish_reason))
    table.add_row("steps", str(len(result.steps)))
    table.add_row("cost_usd", f"{result.cost_usd:.4f}")
    table.add_row("tokens_in/out", f"{result.tokens_in} / {result.tokens_out}")
    table.add_row("duration_ms", str(result.duration_ms))
    console.print(table)
    console.print()
    console.print(result.output)


__all__ = ["register_run_cmd"]
