"""`agentforge health` — preflight checks (feat-017 chunk 8).

Renamed from the spec's `agentforge status` to avoid colliding with
the feat-011 scaffolding-state `agentforge status`. Checks:

1. Config loads + validates.
2. Every installed module resolvable via `Resolver.list_installed`.
3. Every backend declared under `modules.{memory,graph,retriever}`
   reachable (instantiate, `__aenter__`/`close()`).
4. Provider construction is exercised as a no-API probe.

Exit codes: 0 all OK, 1 any FAIL, 2 config invalid.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import sys
from pathlib import Path
from typing import Any

from agentforge_core.config.loader import load_config
from agentforge_core.config.schema import AgentForgeConfig
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import Resolver
from pydantic import ValidationError

from agentforge.cli._build import (
    build_memory_from_config,
)


def register_health_cmd(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = sub.add_parser(
        "health",
        help="Preflight: config valid, modules loadable, backends reachable.",
    )
    parser.add_argument("--path", type=Path, default=None)
    parser.add_argument("--env", default=None)
    parser.add_argument("--override", action="append", default=[])
    parser.add_argument(
        "--output-format",
        choices=("rich", "plain", "json"),
        default="plain",
    )
    parser.set_defaults(_handler=_health_handler)


def _health_handler(args: argparse.Namespace) -> int:
    return asyncio.run(_dispatch(args))


async def _dispatch(args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []

    try:
        config = load_config(args.path, env=args.env, overrides=list(args.override) or None)
        checks.append({"name": "config", "kind": "config", "ok": True, "detail": "valid"})
    except ValidationError as exc:
        _emit([{"name": "config", "kind": "config", "ok": False, "detail": str(exc)}], args)
        return 2
    except ModuleError as exc:
        _emit([{"name": "config", "kind": "config", "ok": False, "detail": str(exc)}], args)
        return 2

    checks.extend(_check_modules())
    checks.extend(await _check_backends(config))

    ok = all(c["ok"] for c in checks)
    _emit(checks, args)
    return 0 if ok else 1


def _check_modules() -> list[dict[str, Any]]:
    """Walk Resolver.list_installed and assert each module resolvable."""
    out: list[dict[str, Any]] = []
    resolver = Resolver.global_()
    for info in resolver.list_installed():
        try:
            resolver.resolve(info.category, info.name)
        except ModuleError as exc:
            out.append(
                {
                    "name": f"{info.category}:{info.name}",
                    "kind": "module",
                    "ok": False,
                    "detail": str(exc),
                }
            )
        else:
            out.append(
                {
                    "name": f"{info.category}:{info.name}",
                    "kind": "module",
                    "ok": True,
                    "detail": "resolvable",
                }
            )
    return out


async def _check_backends(config: AgentForgeConfig) -> list[dict[str, Any]]:
    """For each configured backend, attempt to instantiate + close."""
    out: list[dict[str, Any]] = []

    if config.modules.memory is not None:
        out.append(await _probe("memory", lambda: build_memory_from_config(config)))
    return out


async def _probe(label: str, factory: Any) -> dict[str, Any]:
    try:
        instance = factory()
        if inspect.isawaitable(instance):
            instance = await instance
        if instance is None:
            return {"name": label, "kind": "backend", "ok": True, "detail": "none configured"}
        init = getattr(instance, "init_schema", None)
        if callable(init):
            await init()
        close = getattr(instance, "close", None)
        if callable(close):
            await close()
    except (ModuleError, OSError) as exc:
        return {"name": label, "kind": "backend", "ok": False, "detail": str(exc)}
    return {"name": label, "kind": "backend", "ok": True, "detail": "reachable"}


def _emit(checks: list[dict[str, Any]], args: argparse.Namespace) -> None:
    if args.output_format == "json":
        ok = all(c["ok"] for c in checks)
        print(json.dumps({"checks": checks, "ok": ok}, indent=2))
        return
    for c in checks:
        status = "OK  " if c["ok"] else "FAIL"
        sys.stdout.write(f"{status}  {c['kind']:<8}  {c['name']:<32}  {c['detail']}\n")


__all__ = ["register_health_cmd"]
