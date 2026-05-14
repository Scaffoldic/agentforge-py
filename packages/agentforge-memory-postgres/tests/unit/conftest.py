"""Shared SQL fake for `agentforge-memory-postgres` unit tests.

Production wraps an `asyncpg.Pool`; tests inject this fake which
interprets the limited SQL vocabulary the drivers emit and routes to
in-memory backings (`InMemoryStore` for claims, an `OrderedDict` +
brute-force cosine for vectors). Records every query for assertion.

Live tests against real Postgres live in `tests/integration/`
(gated on `RUN_LIVE_POSTGRES=1`).
"""

from __future__ import annotations

import json
import math
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from agentforge.memory.in_memory import InMemoryStore
from agentforge_core._bm25 import _BM25Index
from agentforge_core.values.claim import Claim


@dataclass
class _Query:
    sql: str
    params: tuple[Any, ...]


@dataclass
class PostgresFakeRunner:
    """Routes the SQL the drivers emit to in-memory backings.

    Multi-modal: handles claims (`claims` table) and vectors
    (`vectors` table). Operation detection is regex-based over the
    queries the drivers actually emit — narrow surface, so easier
    than a real SQL parser.
    """

    memory_backing: InMemoryStore = field(default_factory=InMemoryStore)
    vectors: OrderedDict[str, dict[str, Any]] = field(default_factory=OrderedDict)
    queries: list[_Query] = field(default_factory=list)
    closed: bool = False
    # Tracks whether `init_schema()` ran on the vector store, mirroring
    # how the production driver flips its `_ann` flag.
    vector_schema_init: bool = False
    # feat-024 migration tracking — simulates the
    # `agentforge_migrations` Postgres table.
    migrations_table_exists: bool = False
    applied_migrations: OrderedDict[str, dict[str, Any]] = field(default_factory=OrderedDict)

    async def fetch(self, sql: str, *params: Any) -> list[Any]:
        self.queries.append(_Query(sql, params))
        return await self._dispatch_select(sql, params)

    async def fetchrow(self, sql: str, *params: Any) -> Any | None:
        self.queries.append(_Query(sql, params))
        rows = await self._dispatch_select(sql, params)
        return rows[0] if rows else None

    async def execute(self, sql: str, *params: Any) -> None:
        self.queries.append(_Query(sql, params))
        await self._dispatch_execute(sql, params)

    async def executemany(self, sql: str, args: list[tuple[Any, ...]]) -> None:
        for arg in args:
            self.queries.append(_Query(sql, arg))
            await self._dispatch_execute(sql, arg)

    async def execute_returning_count(self, sql: str, *params: Any) -> int:
        self.queries.append(_Query(sql, params))
        return await self._dispatch_returning_count(sql, params)

    async def close(self) -> None:
        self.closed = True

    async def _dispatch_execute(self, sql: str, params: tuple[Any, ...]) -> None:  # noqa: PLR0911
        s = " ".join(sql.split())
        # Schema bootstrap — record the fact for capability checks.
        if "CREATE TABLE IF NOT EXISTS claims" in s:
            return
        if (
            "CREATE EXTENSION IF NOT EXISTS vector" in s
            or "CREATE TABLE IF NOT EXISTS vectors" in s
        ):
            self.vector_schema_init = True
            return
        if s.startswith("CREATE INDEX"):
            return
        # feat-022 follow-up: tsvector column + GIN index landed via
        # init_schema. No-op for the fake (the BM25 path is computed
        # on-the-fly in _dispatch_vector_lexical).
        if "ALTER TABLE vectors ADD COLUMN IF NOT EXISTS embedding_tsv" in s:
            return
        # feat-024 migration framework — tracking table + applied rows.
        if "CREATE TABLE IF NOT EXISTS agentforge_migrations" in s:
            self.migrations_table_exists = True
            return
        if s.startswith("INSERT INTO agentforge_migrations"):
            migration_id, name, checksum = params
            self.applied_migrations[str(migration_id)] = {
                "id": str(migration_id),
                "name": str(name),
                "checksum": str(checksum),
                "applied_at": datetime.now(UTC),
            }
            return
        # Memory: upsert claim
        if s.startswith("INSERT INTO claims"):
            (
                cid,
                project,
                agent,
                run_id,
                category,
                payload_json,
                supersedes,
                created_at,
            ) = params
            await self.memory_backing.put(
                Claim(
                    id=cid,
                    project=project,
                    agent=agent,
                    run_id=run_id,
                    category=category,
                    payload=json.loads(payload_json),
                    supersedes=supersedes,
                    created_at=_to_datetime(created_at),
                )
            )
            return
        # Vector upsert path
        if s.startswith("INSERT INTO vectors"):
            vid, embedding, text, metadata_json = params
            self.vectors[vid] = {
                "id": vid,
                "embedding": list(embedding),
                "text": text,
                "metadata": _ensure_dict(metadata_json),
            }
            return
        # Vector: delete by ids
        if s.startswith("DELETE FROM vectors WHERE id = ANY"):
            (ids,) = params
            for vid in list(ids):
                self.vectors.pop(vid, None)
            return
        msg = f"PostgresFakeRunner execute: unrecognised SQL: {sql!r}"
        raise AssertionError(msg)

    async def _dispatch_returning_count(
        self,
        sql: str,
        params: tuple[Any, ...],
    ) -> int:
        s = " ".join(sql.split())
        if s.startswith("DELETE FROM claims WHERE"):
            # Driver emits filters in fixed order: run_id, category,
            # older_than. Each is bound to its own $N placeholder.
            cursor = 0
            kwargs: dict[str, Any] = {}
            if "run_id =" in s:
                kwargs["run_id"] = params[cursor]
                cursor += 1
            if "category =" in s:
                kwargs["category"] = params[cursor]
                cursor += 1
            if "created_at <" in s:
                kwargs["older_than"] = _to_datetime(params[cursor])
                cursor += 1
            return await self.memory_backing.delete(**kwargs)
        msg = f"PostgresFakeRunner execute_returning_count: unrecognised SQL: {sql!r}"
        raise AssertionError(msg)

    async def _dispatch_select(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:  # noqa: PLR0911
        s = " ".join(sql.split())
        # Memory: fetch by id
        if s.startswith("SELECT * FROM claims WHERE id = $1"):
            claim = await self.memory_backing.get(params[0])
            return [_claim_record(claim)] if claim else []
        # Memory: filter SELECT
        if s.startswith("SELECT * FROM claims"):
            return await self._dispatch_claim_filter(s, params)
        # Vector: existence probe by ids
        if s.startswith("SELECT id FROM vectors WHERE id = ANY"):
            ids = params[0]
            return [{"id": v} for v in ids if v in self.vectors]
        # Vector: search (ordered by cosine distance)
        if "ORDER BY embedding <=>" in s:
            return await self._dispatch_vector_search(s, params)
        # Vector: lexical search (feat-022 follow-up)
        if "plainto_tsquery" in s or "ts_rank_cd" in s:
            return await self._dispatch_vector_lexical(s, params)
        # feat-024 migration framework
        if "to_regclass" in s:
            (table_name,) = params
            exists = (
                self.migrations_table_exists if table_name == "agentforge_migrations" else False
            )
            return [{"exists_": exists}]
        if s.startswith("SELECT id, name, checksum, applied_at FROM agentforge_migrations"):
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "checksum": row["checksum"],
                    "applied_at": row["applied_at"],
                }
                for row in self.applied_migrations.values()
            ]
        msg = f"PostgresFakeRunner select: unrecognised SQL: {sql!r}"
        raise AssertionError(msg)

    async def _dispatch_claim_filter(self, s: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {}
        # Extract column = $N pairs in order; map by position.
        cols = re.findall(r"(\w+) = \$(\d+)", s)
        for col, idx in cols:
            kwargs[col] = params[int(idx) - 1]
        # LIMIT $N if present.
        m = re.search(r"LIMIT \$(\d+)", s)
        limit_val: int = 100
        if m:
            limit_val = int(params[int(m.group(1)) - 1])
        claims = await self.memory_backing.query(
            project=kwargs.get("project"),
            agent=kwargs.get("agent"),
            category=kwargs.get("category"),
            run_id=kwargs.get("run_id"),
            limit=limit_val,
        )
        return [_claim_record(c) for c in claims]

    async def _dispatch_vector_lexical(
        self, s: str, params: tuple[Any, ...]
    ) -> list[dict[str, Any]]:
        """BM25 stand-in for the production `ts_rank_cd` path.

        Production Postgres uses `plainto_tsquery` + `ts_rank_cd`; the
        fake reuses the framework's `_BM25Index` so unit tests get
        directionally identical ordering without a real Postgres.
        """
        del s
        query: str = params[0]
        metadata_filter = _ensure_dict(params[1])
        limit = int(params[2])

        idx = _BM25Index()
        for v in self.vectors.values():
            idx.add(str(v["id"]), str(v["text"]))
        scored = idx.score(query, limit=max(limit * 4, limit))
        if not scored:
            return []

        top_raw = scored[0][1]
        out: list[dict[str, Any]] = []
        for doc_id, raw in scored:
            v = self.vectors[doc_id]
            meta = dict(v["metadata"])
            if metadata_filter and not _contains(meta, metadata_filter):
                continue
            score = raw / top_raw if top_raw > 0 else 0.0
            out.append(
                {
                    "id": str(v["id"]),
                    "text": str(v["text"]),
                    "metadata": meta,
                    "score": score,
                }
            )
            if len(out) >= limit:
                break
        return out

    async def _dispatch_vector_search(
        self, s: str, params: tuple[Any, ...]
    ) -> list[dict[str, Any]]:
        # Params: (query_vector, metadata_json, limit) — possibly
        # without metadata if filter_metadata is None (then params are
        # query_vector, limit). The driver always passes metadata as
        # `'{}'::jsonb` even for empty filters, so we can rely on the
        # 3-tuple shape.
        query_vec = list(params[0])
        metadata_filter = _ensure_dict(params[1]) if len(params) >= 3 else {}
        limit = int(params[-1])
        q_norm = _l2(query_vec)

        scored: list[tuple[float, str, str, dict[str, Any]]] = []
        for v in self.vectors.values():
            meta = dict(v["metadata"])
            if metadata_filter and not _contains(meta, metadata_filter):
                continue
            emb = _l2(list(v["embedding"]))
            if len(emb) != len(q_norm):
                continue
            sim = sum(a * b for a, b in zip(q_norm, emb, strict=True))
            score = max(0.0, min(1.0, sim))
            scored.append((score, str(v["id"]), str(v["text"]), meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": vid, "text": text, "metadata": meta, "score": score}
            for score, vid, text, meta in scored[:limit]
        ]


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _claim_record(claim: Claim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "project": claim.project,
        "agent": claim.agent,
        "run_id": claim.run_id,
        "category": claim.category,
        "payload": json.dumps(claim.payload),
        "supersedes": claim.supersedes,
        "created_at": claim.created_at,
    }


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _ensure_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value) or {}
    return {}


def _l2(v: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v] if norm > 0 else v


def _contains(meta: dict[str, Any], filter_md: dict[str, Any]) -> bool:
    return all(meta.get(k) == v for k, v in filter_md.items())


@pytest.fixture
def postgres_fake_runner() -> PostgresFakeRunner:
    return PostgresFakeRunner()
