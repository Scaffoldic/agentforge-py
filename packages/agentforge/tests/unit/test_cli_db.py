"""Tests for `agentforge db` subcommands (feat-017 chunk 7)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from agentforge import InMemoryStore
from agentforge.cli.main import main
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.resolver import register
from agentforge_core.values.claim import Claim

_SHARED: dict[str, InMemoryStore] = {}


class _SharedInMemoryStore(MemoryStore):
    """A registered MemoryStore backed by a module-level singleton so
    the CLI handler (which constructs a fresh one each call) operates
    against the same data each test sees."""

    def __init__(self) -> None:
        if "store" not in _SHARED:
            _SHARED["store"] = InMemoryStore()

    @property
    def _inner(self) -> InMemoryStore:
        return _SHARED["store"]

    async def put(self, claim: Claim) -> str:
        return await self._inner.put(claim)

    async def get(self, claim_id: str) -> Claim | None:
        return await self._inner.get(claim_id)

    async def query(self, **kwargs: Any) -> list[Claim]:
        return await self._inner.query(**kwargs)

    async def supersede(self, old_id: str, new_claim: Claim) -> str:
        return await self._inner.supersede(old_id, new_claim)

    def stream(self, **kwargs: Any) -> AsyncIterator[Claim]:
        return self._inner.stream(**kwargs)

    async def delete(
        self,
        *,
        run_id: str | None = None,
        older_than: datetime | None = None,
        category: str | None = None,
    ) -> int:
        return await self._inner.delete(
            run_id=run_id,
            older_than=older_than,
            category=category,
        )

    async def close(self) -> None:
        await self._inner.close()


@pytest.fixture(autouse=True)
def _shared_store() -> None:
    _SHARED.clear()
    register("memory", "shared-in-mem")(_SharedInMemoryStore)


def _write_cfg(tmp_path: Path) -> Path:
    cfg = tmp_path / "agentforge.yaml"
    cfg.write_text(
        "modules:\n  memory: {driver: shared-in-mem}\n",
        encoding="utf-8",
    )
    return cfg


def test_db_migrate_no_op_for_in_memory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_cfg(tmp_path)
    code = main(["db", "--path", str(cfg), "migrate"])
    out = capsys.readouterr().out
    assert code == 0
    assert "nothing to migrate" in out


def test_db_backup_then_restore_roundtrip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_cfg(tmp_path)
    store = _SharedInMemoryStore()  # forces the singleton

    asyncio.run(
        store.put(Claim(run_id="r1", project="p", agent="a", category="cat", payload={"v": 1}))
    )
    asyncio.run(
        store.put(Claim(run_id="r2", project="p", agent="a", category="cat", payload={"v": 2}))
    )
    dump = tmp_path / "dump.jsonl"
    code = main(["db", "--path", str(cfg), "backup", "--to", str(dump)])
    capsys.readouterr()
    assert code == 0
    assert dump.exists()
    assert dump.read_text(encoding="utf-8").count("\n") == 2

    # Wipe and restore.
    asyncio.run(store.delete(category="cat"))
    code = main(["db", "--path", str(cfg), "restore", "--from", str(dump)])
    assert code == 0
    rows = asyncio.run(store.query())
    assert len(rows) == 2


def test_db_purge_by_category_yes_skips_confirm(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_cfg(tmp_path)
    store = _SharedInMemoryStore()

    asyncio.run(
        store.put(Claim(run_id="r1", project="p", agent="a", category="ephemeral", payload={}))
    )
    asyncio.run(store.put(Claim(run_id="r1", project="p", agent="a", category="keep", payload={})))
    code = main(["db", "--path", str(cfg), "purge", "--category", "ephemeral", "--yes"])
    out = capsys.readouterr().out
    assert code == 0
    assert "removed 1" in out
    remaining = asyncio.run(store.query())
    assert len(remaining) == 1
    assert remaining[0].category == "keep"


def test_db_query_dsl_filters_results(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_cfg(tmp_path)
    store = _SharedInMemoryStore()

    asyncio.run(store.put(Claim(run_id="r1", project="p", agent="a1", category="X", payload={})))
    asyncio.run(store.put(Claim(run_id="r1", project="p", agent="a2", category="Y", payload={})))
    code = main(["db", "--path", str(cfg), "query", "category:X"])
    out = capsys.readouterr().out
    assert code == 0
    assert "agent=a1" in out
    assert "agent=a2" not in out


def test_db_query_unknown_key_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = _write_cfg(tmp_path)
    code = main(["db", "--path", str(cfg), "query", "bogus:x"])
    err = capsys.readouterr().err
    assert code == 1
    assert "unknown query key" in err
