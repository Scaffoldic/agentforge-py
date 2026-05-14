"""`Neo4jMemoryStore` — `MemoryStore` over Neo4j via the `neo4j` async
driver.

Claims map to `(:Claim {id, project, agent, run_id, category, payload,
supersedes, created_at})` nodes. Filter queries become parameterised
Cypher WHERE chains; `supersede` adds a `[:SUPERSEDES]` edge from the
new claim to the old, in addition to setting the `supersedes` property
(so callers can both read the property and traverse the chain via
graph queries).
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
from neo4j import AsyncGraphDatabase

from agentforge_memory_neo4j._migrator import Neo4jMigrator
from agentforge_memory_neo4j._runner import CypherRunner, _Neo4jDriverRunner

_CLAIM_LABEL = "Claim"


class Neo4jMemoryStore(MemoryStore):
    """`MemoryStore` over Neo4j. Uses a dedicated `:Claim` label so it
    can coexist with `Neo4jGraphStore` in the same database without
    collision."""

    def __init__(self, *, runner: CypherRunner) -> None:
        self._r = runner

    @classmethod
    async def from_url(
        cls,
        url: str,
        *,
        auth: tuple[str, str],
        database: str = "neo4j",
    ) -> Neo4jMemoryStore:
        driver = AsyncGraphDatabase.driver(url, auth=auth)
        return cls(runner=_Neo4jDriverRunner(driver, database))

    async def __aenter__(self) -> Neo4jMemoryStore:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    def migrator(self) -> Neo4jMigrator:
        """Return a `Neo4jMigrator` configured against the package's
        bundled migrations directory (feat-024)."""
        return Neo4jMigrator(self._r)

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
        cypher = (
            f"MERGE (c:{_CLAIM_LABEL} {{id: $id}}) "
            "SET c.project = $project, c.agent = $agent, c.run_id = $run_id, "
            "c.category = $category, c.payload = $payload, "
            "c.supersedes = $supersedes, c.created_at = $created_at"
        )
        await self._r.execute_write(
            cypher,
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
        rows = await self._r.execute_read(
            f"MATCH (c:{_CLAIM_LABEL} {{id: $id}}) RETURN c", {"id": claim_id}
        )
        if not rows:
            return None
        return _row_to_claim(rows[0]["c"])

    async def query(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[Claim]:
        cypher, params = _build_filter_cypher(
            project=project,
            agent=agent,
            category=category,
            run_id=run_id,
            limit=limit,
        )
        rows = await self._r.execute_read(cypher, params)
        return [_row_to_claim(row["c"]) for row in rows]

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
        new_id = await self.put(new_claim)
        # Also write the graph edge so graph queries can traverse the chain.
        await self._r.execute_write(
            f"MATCH (n:{_CLAIM_LABEL} {{id: $new}}) "
            f"MATCH (o:{_CLAIM_LABEL} {{id: $old}}) "
            "MERGE (n)-[:SUPERSEDES]->(o)",
            {"new": new_id, "old": old_id},
        )
        return new_id

    def stream(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
    ) -> AsyncIterator[Claim]:
        cypher, params = _build_filter_cypher(
            project=project,
            agent=agent,
            category=category,
            run_id=run_id,
            limit=None,
        )

        async def _agen() -> AsyncIterator[Claim]:
            rows = await self._r.execute_read(cypher, params)
            for row in rows:
                yield _row_to_claim(row["c"])

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
            where.append("c.run_id = $run_id")
            params["run_id"] = run_id
        if category is not None:
            where.append("c.category = $category")
            params["category"] = category
        if older_than is not None:
            where.append("c.created_at < $older_than")
            params["older_than"] = older_than.isoformat()
        cypher = (
            f"MATCH (c:{_CLAIM_LABEL}) WHERE "
            + " AND ".join(where)
            + " WITH count(c) AS n, collect(c) AS cs "
            "FOREACH (x IN cs | DETACH DELETE x) RETURN n"
        )
        rows = await self._r.execute_write(cypher, params)
        return int(rows[0]["n"]) if rows else 0

    def capabilities(self) -> set[str]:
        return {"transactions", "graph"}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _row_to_claim(record_node: Any) -> Claim:
    """Convert a neo4j Claim node record into a `Claim`."""
    props = dict(record_node)
    return Claim(
        id=props["id"],
        project=props["project"],
        agent=props["agent"],
        run_id=props["run_id"],
        category=props["category"],
        payload=json.loads(props["payload"]),
        supersedes=props.get("supersedes"),
        created_at=datetime.fromisoformat(props["created_at"]),
    )


def _build_filter_cypher(
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
        where.append("c.project = $project")
        params["project"] = project
    if agent is not None:
        where.append("c.agent = $agent")
        params["agent"] = agent
    if category is not None:
        where.append("c.category = $category")
        params["category"] = category
    if run_id is not None:
        where.append("c.run_id = $run_id")
        params["run_id"] = run_id

    cypher = f"MATCH (c:{_CLAIM_LABEL})"
    if where:
        cypher += " WHERE " + " AND ".join(where)
    cypher += " RETURN c ORDER BY c.created_at"
    if limit is not None:
        cypher += " LIMIT $limit"
        params["limit"] = limit
    return cypher, params


__all__ = ["Neo4jMemoryStore"]
