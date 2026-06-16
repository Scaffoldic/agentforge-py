"""`agentforge db` subcommands (feat-017 chunk 7).

Routed to the active `MemoryStore`:

    agentforge db migrate                  # call init_schema if present
    agentforge db backup --to FILE|-       # JSONL dump of every claim
    agentforge db restore --from FILE      # bulk put() from a JSONL file
    agentforge db purge --older-than 30d   # delete by filter
                       --run-id RUN_ID
                       --category CAT
    agentforge db query 'category:X agent:Y limit:50'

`db migrate` is a no-op (info + exit 0) for drivers without an
`init_schema` method (InMemoryStore, SqliteMemoryStore which creates
its schema eagerly).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.claim import Claim

from agentforge.cli._build import build_memory_from_config


def register_db_cmd(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = sub.add_parser(
        "db",
        help="Operate on the configured memory store (migrate / backup / restore / purge / query).",
    )
    parser.add_argument("--path", type=Path, default=None)
    parser.add_argument("--env", default=None)
    parser.add_argument("--override", action="append", default=[])
    db_sub = parser.add_subparsers(dest="db_command", required=True)

    db_sub.add_parser(
        "migrate",
        help="Apply pending schema migrations (feat-024) or call init_schema fallback.",
    )
    db_sub.add_parser(
        "migrate-status",
        help="List applied + pending migrations for the configured store (feat-024).",
    )

    backup = db_sub.add_parser("backup", help="Dump every claim to JSONL.")
    backup.add_argument("--to", required=True, help="Output path or '-' for stdout.")

    restore = db_sub.add_parser("restore", help="Bulk put() claims from a JSONL file.")
    restore.add_argument("--from", dest="src", required=True, help="Input path or '-'.")

    purge = db_sub.add_parser("purge", help="Delete claims by filter.")
    purge.add_argument("--older-than", default=None, help="Duration like 30d, 24h, 90m.")
    purge.add_argument("--run-id", default=None)
    purge.add_argument("--category", default=None)
    purge.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")

    query = db_sub.add_parser("query", help="Tiny DSL → MemoryStore.query.")
    query.add_argument("dsl", help="Tokens like 'category:X agent:Y run_id:Z'.")
    query.add_argument("--limit", type=int, default=100)
    query.add_argument(
        "--output-format",
        choices=("rich", "json", "plain"),
        default="plain",
    )

    parser.set_defaults(_handler=_db_handler)


def _db_handler(args: argparse.Namespace) -> int:
    return asyncio.run(_dispatch(args))


async def _dispatch(args: argparse.Namespace) -> int:
    from agentforge_core.config.loader import load_config  # noqa: PLC0415

    config = load_config(args.path, env=args.env, overrides=list(args.override) or None)
    memory = await build_memory_from_config(config)
    if memory is None:
        sys.stderr.write("agentforge db: modules.memory must be configured.\n")
        return 1

    dispatch = {
        "migrate": _do_migrate,
        "migrate-status": _do_migrate_status,
        "backup": _do_backup,
        "restore": _do_restore,
        "purge": _do_purge,
        "query": _do_query,
    }
    handler = dispatch[args.db_command]
    return await handler(memory, args)


async def _do_migrate(memory: Any, args: argparse.Namespace) -> int:
    """Apply pending migrations via the feat-024 framework when the
    driver exposes a `migrator()` method; otherwise fall back to
    legacy `init_schema()`."""
    del args
    migrator_factory = getattr(memory, "migrator", None)
    if callable(migrator_factory):
        migrator = migrator_factory()
        applied = await migrator.apply_pending()
        if not applied:
            sys.stdout.write("  → schema up to date; no pending migrations.\n")
        else:
            for migration in applied:
                sys.stdout.write(f"  → applied {migration.id}_{migration.name}\n")
        return 0
    init = getattr(memory, "init_schema", None)
    if not callable(init):
        sys.stdout.write(
            "  → driver has no migrator()/init_schema(); nothing to migrate.\n",
        )
        return 0
    await init()
    sys.stdout.write("  → schema initialised (legacy init_schema path).\n")
    return 0


async def _do_migrate_status(memory: Any, args: argparse.Namespace) -> int:
    """List applied + pending migrations for the configured store
    (feat-024). Drivers without a `migrator()` method print a
    diagnostic and exit 0."""
    del args
    migrator_factory = getattr(memory, "migrator", None)
    if not callable(migrator_factory):
        sys.stdout.write(
            "  → driver has no migrator() method; cannot report status.\n",
        )
        return 0
    migrator = migrator_factory()
    statuses = await migrator.status()
    if not statuses:
        sys.stdout.write("  → no migrations bundled with this driver.\n")
        return 0
    for status in statuses:
        if status.applied:
            checksum_flag = "✓" if status.checksum_match else "✗"
            sys.stdout.write(
                f"  ✓ {status.migration.id}_{status.migration.name} "
                f"(applied {status.applied_at}; checksum {checksum_flag})\n"
            )
        else:
            sys.stdout.write(f"    {status.migration.id}_{status.migration.name} — pending\n")
    return 0


async def _do_backup(memory: Any, args: argparse.Namespace) -> int:
    target = args.to
    out_stream: Any = (
        sys.stdout if target == "-" else Path(target).open("w", encoding="utf-8")  # noqa: SIM115, ASYNC230 — closed in finally
    )
    count = 0
    try:
        async for claim in memory.stream():
            out_stream.write(claim.model_dump_json() + "\n")
            count += 1
    finally:
        if target != "-":
            out_stream.close()
    sys.stderr.write(f"  → wrote {count} claims.\n")
    return 0


async def _do_restore(memory: Any, args: argparse.Namespace) -> int:
    src = args.src
    text = (
        sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")  # noqa: ASYNC240 — CLI one-shot
    )
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        await memory.put(Claim.model_validate_json(stripped))
        count += 1
    sys.stdout.write(f"  → restored {count} claims.\n")
    return 0


async def _do_purge(memory: Any, args: argparse.Namespace) -> int:
    older_than = _parse_duration(args.older_than) if args.older_than else None
    if args.run_id is None and args.category is None and older_than is None:
        sys.stderr.write(
            "agentforge db purge: pass at least one of --older-than / --run-id / --category.\n"
        )
        return 1
    if not args.yes:
        sys.stderr.write("Proceed? [y/N]: ")
        sys.stderr.flush()
        confirm = sys.stdin.readline().strip().lower()
        if confirm not in {"y", "yes"}:
            sys.stderr.write("cancelled.\n")
            return 1
    try:
        removed = await memory.delete(
            run_id=args.run_id,
            older_than=older_than,
            category=args.category,
        )
    except ModuleError as exc:
        sys.stderr.write(f"agentforge db purge: {exc}\n")
        return 1
    sys.stdout.write(f"  → removed {removed} claims.\n")
    return 0


async def _do_query(memory: Any, args: argparse.Namespace) -> int:
    try:
        filters = _parse_dsl(args.dsl)
    except ValueError as exc:
        sys.stderr.write(f"agentforge db query: {exc}\n")
        return 1
    claims = await memory.query(limit=args.limit, **filters)
    if args.output_format == "json":
        print(json.dumps([c.model_dump(mode="json") for c in claims], indent=2))
    else:
        for c in claims:
            print(f"{c.id}  {c.category:<20} run={c.run_id:<26} agent={c.agent}")
    return 0


_DURATION_RE = re.compile(r"^(\d+)([smhd])$")


def _parse_duration(s: str) -> datetime:
    m = _DURATION_RE.match(s)
    if m is None:
        msg = f"--older-than expects e.g. '30d', '24h', '15m'; got {s!r}."
        raise ValueError(msg)
    n, unit = int(m.group(1)), m.group(2)
    seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit] * n
    return datetime.now(UTC) - timedelta(seconds=seconds)


_QUERY_KEYS = {"category", "agent", "project", "run_id"}


def _parse_dsl(dsl: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for token in dsl.split():
        if ":" not in token:
            msg = f"token {token!r} not in key:value form."
            raise ValueError(msg)
        k, v = token.split(":", 1)
        if k not in _QUERY_KEYS:
            msg = f"unknown query key {k!r}; supported: {sorted(_QUERY_KEYS)}."
            raise ValueError(msg)
        out[k] = v
    return out


__all__ = ["register_db_cmd"]
