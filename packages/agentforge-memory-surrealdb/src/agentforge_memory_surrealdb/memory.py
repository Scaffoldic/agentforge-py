"""`SurrealMemoryStore` — `MemoryStore` over SurrealDB.

Claims map to records in the `af_claim` table. Filter queries become
parameterised SurrealQL WHERE chains. The driver returns claims in
insertion order via the `created_at` timestamp.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from types import TracebackType
from typing import Any

from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.claim import Claim
from surrealdb import AsyncSurreal

from agentforge_memory_surrealdb._migrator import SurrealMigrator
from agentforge_memory_surrealdb._runner import SurrealRunner, _SurrealClientRunner

# Table name is a framework constant, never derived from user input;
# the S608 noqa annotations below are explicit acknowledgements of
# that fact, not relaxations of the lint surface.
_CLAIM_TABLE = "af_claim"

_INIT_SCHEMA_QUERY = (
    f"DEFINE TABLE IF NOT EXISTS {_CLAIM_TABLE} SCHEMALESS;"
    f"DEFINE INDEX IF NOT EXISTS {_CLAIM_TABLE}_id_idx "
    f"ON {_CLAIM_TABLE} FIELDS af_id UNIQUE;"
    f"DEFINE INDEX IF NOT EXISTS {_CLAIM_TABLE}_proj_agent_idx "
    f"ON {_CLAIM_TABLE} FIELDS project, agent;"
)

_UPSERT_CLAIM_QUERY = (
    f"UPSERT type::thing('{_CLAIM_TABLE}', $id) CONTENT "
    "{ af_id: $id, project: $project, agent: $agent, "
    "run_id: $run_id, category: $category, payload: $payload, "
    "supersedes: $supersedes, created_at: $created_at }"
)
_SELECT_CLAIM_BY_ID = f"SELECT * FROM {_CLAIM_TABLE} WHERE af_id = $id LIMIT 1"  # noqa: S608  # nosec B608


class SurrealMemoryStore(MemoryStore):
    """`MemoryStore` over SurrealDB."""

    def __init__(self, *, runner: SurrealRunner) -> None:
        self._r = runner

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        namespace: str = "agentforge",
        database: str = "default",
        auth: tuple[str, str] | None = None,
    ) -> SurrealMemoryStore:
        client = AsyncSurreal(url)
        if auth is not None:
            await client.signin({"username": auth[0], "password": auth[1]})
        await client.use(namespace, database)
        return cls(runner=_SurrealClientRunner(client))

    @classmethod
    async def from_config(
        cls,
        *,
        url: str,
        namespace: str = "agentforge",
        database: str = "default",
        auth: tuple[str, str] | list[str] | None = None,
    ) -> SurrealMemoryStore:  # pragma: no cover — exercised only with `-m live`.
        """Build from a `modules.memory.config` block (bug-022).

        Async config-driven factory matching the framework convention.
        `auth` arrives from YAML as a 2-item list (or omitted); coerce
        to the tuple `from_url` expects.
        """
        auth_tuple = (auth[0], auth[1]) if auth is not None else None
        return await cls.from_url(url, namespace=namespace, database=database, auth=auth_tuple)

    async def __aenter__(self) -> SurrealMemoryStore:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def migrator(self) -> SurrealMigrator:
        """Return a `SurrealMigrator` configured against the package's
        bundled migrations directory (feat-024)."""
        return SurrealMigrator(self._r)

    async def init_schema(self) -> None:
        """Apply every bundled migration (idempotent). Opt-in.

        Delegates to the feat-024 migration framework.
        """
        await self.migrator().apply_pending()

    async def close(self) -> None:
        await self._r.close()

    # ------------------------------------------------------------------
    # MemoryStore contract
    # ------------------------------------------------------------------

    async def put(self, claim: Claim) -> str:
        await self._r.query(
            _UPSERT_CLAIM_QUERY,
            {
                "id": claim.id,
                "project": claim.project,
                "agent": claim.agent,
                "run_id": claim.run_id,
                "category": claim.category,
                "payload": json.dumps(claim.payload),
                "supersedes": claim.supersedes,
                "created_at": claim.created_at.isoformat(),
            },
        )
        return claim.id

    async def get(self, claim_id: str) -> Claim | None:
        rows = await self._r.query(_SELECT_CLAIM_BY_ID, {"id": claim_id})
        records = _flatten(rows)
        if not records:
            return None
        return _record_to_claim(records[0])

    async def query(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[Claim]:
        surql, params = _build_filter_query(
            project=project,
            agent=agent,
            category=category,
            run_id=run_id,
            limit=limit,
        )
        rows = await self._r.query(surql, params)
        return [_record_to_claim(r) for r in _flatten(rows)]

    async def supersede(self, old_id: str, new_claim: Claim) -> str:
        existing = await self.get(old_id)
        if existing is None:
            msg = f"Cannot supersede unknown claim id: {old_id!r}"
            raise ModuleError(msg)
        if new_claim.supersedes is None:
            new_claim = new_claim.model_copy(update={"supersedes": old_id})
        elif new_claim.supersedes != old_id:
            msg = f"new_claim.supersedes={new_claim.supersedes!r} does not match old_id={old_id!r}"
            raise ModuleError(msg)
        return await self.put(new_claim)

    def stream(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
    ) -> AsyncIterator[Claim]:
        surql, params = _build_filter_query(
            project=project,
            agent=agent,
            category=category,
            run_id=run_id,
            limit=None,
        )

        async def _agen() -> AsyncIterator[Claim]:
            rows = await self._r.query(surql, params)
            for r in _flatten(rows):
                yield _record_to_claim(r)

        return _agen()

    async def delete(
        self,
        *,
        run_id: str | None = None,
        older_than: datetime | None = None,
        category: str | None = None,
    ) -> int:
        if run_id is None and older_than is None and category is None:
            msg = "delete() requires at least one filter; refusing to wipe every claim."
            raise ModuleError(msg)
        where: list[str] = []
        params: dict[str, Any] = {}
        if run_id is not None:
            where.append("run_id = $run_id")
            params["run_id"] = run_id
        if category is not None:
            where.append("category = $category")
            params["category"] = category
        if older_than is not None:
            where.append("created_at < $older_than")
            params["older_than"] = older_than.isoformat()
        surql = (
            f"DELETE FROM {_CLAIM_TABLE} WHERE "  # noqa: S608  # nosec B608
            + " AND ".join(where)
            + " RETURN BEFORE"
        )
        rows = await self._r.query(surql, params)
        return len(_flatten(rows))

    def capabilities(self) -> set[str]:
        return {"transactions"}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _flatten(rows: list[Any]) -> list[dict[str, Any]]:
    if not rows:
        return []
    flat: list[dict[str, Any]] = []
    for item in rows:
        if isinstance(item, dict):
            flat.append(item)
        elif isinstance(item, list):
            flat.extend(x for x in item if isinstance(x, dict))
    return flat


def _record_to_claim(record: dict[str, Any]) -> Claim:
    return Claim(
        id=str(record["af_id"]),
        project=str(record["project"]),
        agent=str(record["agent"]),
        run_id=str(record["run_id"]),
        category=str(record["category"]),
        payload=json.loads(record["payload"]),
        supersedes=record.get("supersedes"),
        created_at=datetime.fromisoformat(str(record["created_at"])),
    )


def _build_filter_query(
    *,
    project: str | None,
    agent: str | None,
    category: str | None,
    run_id: str | None,
    limit: int | None,
) -> tuple[str, dict[str, Any]]:
    where: list[str] = []
    params: dict[str, Any] = {}
    if project is not None:
        where.append("project = $project")
        params["project"] = project
    if agent is not None:
        where.append("agent = $agent")
        params["agent"] = agent
    if category is not None:
        where.append("category = $category")
        params["category"] = category
    if run_id is not None:
        where.append("run_id = $run_id")
        params["run_id"] = run_id

    surql = f"SELECT * FROM {_CLAIM_TABLE}"  # noqa: S608  # nosec B608 — table is a constant
    if where:
        surql += " WHERE " + " AND ".join(where)
    surql += " ORDER BY created_at"
    if limit is not None:
        surql += " LIMIT $limit"
        params["limit"] = limit
    return surql, params


__all__ = ["SurrealMemoryStore"]
