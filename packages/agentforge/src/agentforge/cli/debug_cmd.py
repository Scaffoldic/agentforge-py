"""`agentforge debug` — interactive replay REPL (feat-017 chunk 6).

    agentforge debug --replay <RUN_ID> [--path agentforge.yaml]

Loads `category="__step"` claims for the run, exposes a `cmd.Cmd`
prompt with:

    step / s        advance to the next step
    back / b        rewind one step
    state           print the current step's payload
    inspect FIELD   print payload[FIELD] (dotted-path supported)
    steps           list all step kinds + indices
    quit / q        exit

No external dependencies — uses stdlib `cmd.Cmd`.
"""

from __future__ import annotations

import argparse
import asyncio
import cmd
import json
import sys
from pathlib import Path
from typing import IO, Any

from agentforge.cli._build import build_memory_from_config
from agentforge.recording import STEP_CATEGORY


def register_debug_cmd(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = sub.add_parser(
        "debug",
        help="Interactive REPL to step through a recorded run.",
    )
    parser.add_argument("--replay", required=True, metavar="RUN_ID")
    parser.add_argument("--path", type=Path, default=None)
    parser.add_argument("--env", default=None)
    parser.add_argument("--override", action="append", default=[])
    parser.set_defaults(_handler=_debug_handler)


def _debug_handler(args: argparse.Namespace) -> int:
    return asyncio.run(_dispatch(args))


async def _dispatch(args: argparse.Namespace) -> int:
    from agentforge_core.config.loader import load_config  # noqa: PLC0415

    config = load_config(args.path, env=args.env, overrides=list(args.override) or None)
    memory = await build_memory_from_config(config)
    if memory is None:
        sys.stderr.write("agentforge debug: modules.memory must be configured.\n")
        return 1
    steps = await memory.query(category=STEP_CATEGORY, run_id=args.replay, limit=10_000)
    if not steps:
        sys.stderr.write(f"agentforge debug: no steps recorded for run_id={args.replay!r}.\n")
        return 1
    repl = _ReplayREPL([s.payload for s in steps])
    repl.cmdloop()
    return 0


class _ReplayREPL(cmd.Cmd):
    """Interactive replay stepper. Output is plain text — no Rich."""

    intro = "agentforge debug — recorded-run replay. Type 'help' for commands."
    prompt = "(agentforge) "

    def __init__(
        self,
        steps: list[dict[str, Any]],
        *,
        stdin: IO[str] | None = None,
        stdout: IO[str] | None = None,
    ) -> None:
        super().__init__(stdin=stdin, stdout=stdout)
        self._steps = steps
        self._cursor = 0

    def do_step(self, arg: str) -> bool:
        del arg
        if self._cursor >= len(self._steps):
            self._w("END of recording.\n")
            return False
        self._w(_format_step(self._cursor, self._steps[self._cursor]))
        self._cursor += 1
        return False

    do_s = do_step

    def do_back(self, arg: str) -> bool:
        del arg
        if self._cursor <= 0:
            self._w("at start.\n")
            return False
        self._cursor -= 1
        self._w(_format_step(self._cursor, self._steps[self._cursor]))
        return False

    do_b = do_back

    def do_state(self, arg: str) -> bool:
        del arg
        if self._cursor == 0:
            self._w("no step entered yet.\n")
            return False
        idx = self._cursor - 1
        self._w(json.dumps(self._steps[idx], indent=2) + "\n")
        return False

    def do_inspect(self, arg: str) -> bool:
        if self._cursor == 0:
            self._w("no step entered yet.\n")
            return False
        idx = self._cursor - 1
        payload: Any = self._steps[idx]
        for part in arg.split("."):
            if not part:
                continue
            if isinstance(payload, dict) and part in payload:
                payload = payload[part]
            else:
                self._w(f"no such field: {arg}\n")
                return False
        self._w(json.dumps(payload, indent=2) + "\n")
        return False

    def do_steps(self, arg: str) -> bool:
        del arg
        for i, s in enumerate(self._steps):
            self._w(f"  {i:3d}  {s['kind']:<8}  iter={s['iteration']}\n")
        return False

    def do_quit(self, arg: str) -> bool:
        del arg
        return True

    do_q = do_quit
    do_EOF = do_quit  # noqa: N815 — cmd.Cmd protocol uses this exact name

    def _w(self, text: str) -> None:
        out = self.stdout or sys.stdout
        out.write(text)
        out.flush()


_CONTENT_PREVIEW_LEN = 80
_CONTENT_TRUNCATE_AT = 77


def _format_step(idx: int, payload: dict[str, Any]) -> str:
    line = f"[{idx:3d}] kind={payload.get('kind')} iter={payload.get('iteration')}"
    content = payload.get("content")
    if isinstance(content, str):
        preview = (
            content
            if len(content) <= _CONTENT_PREVIEW_LEN
            else content[:_CONTENT_TRUNCATE_AT] + "..."
        )
        line += f"  content={preview!r}"
    elif content is not None:
        line += f"  content={type(content).__name__}"
    return line + "\n"


__all__ = ["register_debug_cmd"]
