# Design Doc: Persistence & ORM layer

## Metadata

| Field | Value |
|---|---|
| **Title** | Persistence & ORM — unified MemoryStore across SQLite, Postgres, SurrealDB, Neo4j |
| **Status** | draft |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Last updated** | 2026-05-09 |
| **Supersedes** | none |
| **Superseded by** | none |
| **Related features** | feat-005 (memory & persistence), feat-001 (core contracts), feat-010 (module system) |

---

## 1. Context

An agent that runs once and forgets everything is fine for demos and useless in
production. Production agents need to:

- Remember what they have already seen (dedupe repeat work, don't re-process the
  same PR / ticket / document).
- Sustain corrections across runs (a developer flagged finding X as wrong; never
  surface it again).
- Share findings with sibling agents (one agent's output is another agent's input).
- Walk relationships across findings (this finding supersedes that one; this issue
  spans these three files; this fact was learned from that source).

We could ship one driver. We could ship four drivers with four ABCs. Neither is
right. We ship **one ABC** with **multiple drivers**, plus a **graph extension**
where the data model needs it.

The reason this is in its own design doc rather than a feature doc: the contract
shape affects every agent that uses persistence and every future driver. Getting
this shape right is a one-time decision; getting it wrong costs every consumer.

## 2. Goals

- A developer writes one piece of code that works against any of the four
  supported backends.
- Switching backends is a config edit + driver install + migration. No business
  logic changes.
- The default (in-memory) backend in `agentforge` lets a brand-new agent run
  without touching a database.
- A graph workload (relationships, traversals) is supported on the backends that
  natively do graphs (SurrealDB, Neo4j) and clearly unsupported on the backends
  that don't (SQLite, Postgres) — no half-broken emulation.
- Migrations are versioned, idempotent, and shipped with the driver — not invented
  by each agent.

## 3. Non-goals

- A general-purpose ORM. We are not competing with SQLAlchemy or Prisma.
  AgentForge's persistence layer stores **claims** and **evidence** — a small,
  well-known schema. Agents that need full ORM access for their own tables use
  SQLAlchemy / Prisma alongside AgentForge; the framework does not get in the way.
- Cross-backend transactions. We do not promise atomicity across, say, SQLite +
  Neo4j; the data model is single-store per run.
- Vector search. Embeddings + retrieval is a separate concern; if a backend (e.g.
  Postgres + pgvector, SurrealDB) supports it, the driver may expose it as an
  optional capability — but the core contract is claim CRUD, not retrieval.

## 4. Proposal

### 4.1 The data model

Two record types, simple and stable:

```
Claim
─────
  id           ULID           framework-generated, stable across supersessions
  run_id       UUID           which run produced this
  project      str            namespace (multi-agent isolation)
  agent        str            which agent wrote it
  category     str            "finding" | "decision" | "fact" | "memo"
  payload      JSON           the actual content (Finding.to_dict() or similar)
  supersedes   ULID | null    if this claim replaces another
  created_at   datetime
  metadata     JSON           free-form module-specific data

Edge (graph backends only)
─────
  source       Claim.id
  target       Claim.id
  kind         str            "supersedes" | "references" | "spans" | "derived_from" | <custom>
  metadata     JSON
```

This is the contract. Every backend stores exactly these two record types,
addressable by the same operations.

### 4.2 The MemoryStore ABC

```python
# agentforge_core/contracts/memory.py
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

class MemoryStore(ABC):
    """Unified persistence for claims. Required.

    Every driver implements this. SQL and document drivers fully support it.
    Graph drivers also implement GraphStore (below).
    """

    @abstractmethod
    async def put(self, claim: Claim) -> str: ...
    @abstractmethod
    async def get(self, claim_id: str) -> Claim | None: ...
    @abstractmethod
    async def query(
        self,
        *,
        project: str | None = None,
        agent: str | None = None,
        category: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[Claim]: ...
    @abstractmethod
    async def supersede(self, old_id: str, new_claim: Claim) -> str: ...
    @abstractmethod
    async def stream(self, **filters: Any) -> AsyncIterator[Claim]: ...
    @abstractmethod
    async def close(self) -> None: ...

    def capabilities(self) -> set[str]:
        """Drivers declare optional capabilities — graph, vector, fts, transactions."""
        return set()


class GraphStore(ABC):
    """Optional. Only graph-capable drivers (surrealdb, neo4j) implement this."""

    @abstractmethod
    async def link(self, source_id: str, target_id: str, kind: str, **metadata: Any) -> None: ...
    @abstractmethod
    async def neighbours(self, claim_id: str, *, kind: str | None = None, depth: int = 1) -> list[Claim]: ...
    @abstractmethod
    async def traverse(self, claim_id: str, query: GraphQuery) -> list[Claim]: ...
```

A driver implementing only `MemoryStore` cannot serve graph queries. Calling graph
operations on a non-graph driver raises `CapabilityNotSupported`, which the
framework checks at startup (P11) — not at the moment a query runs.

### 4.3 Drivers — what each one is good for

| Driver | Module package | When to pick it |
|---|---|---|
| **InMemory** | `agentforge` (default) | Tests, demos, ephemeral runs. Zero config. Loses data on exit. |
| **SQLite** | `agentforge-memory-sqlite` | Single-process agents. One file. No infra. Good for first production deploy. Implements `MemoryStore`; no graph. |
| **Postgres** | `agentforge-memory-postgres` | Multi-process / multi-worker agents. Mature ops story. JSONB + GIN for payload queries. Optional pgvector for embeddings. Implements `MemoryStore`; emulates basic graph only via recursive CTE if `capabilities` includes `graph` (off by default — recommend Neo4j or SurrealDB instead). |
| **SurrealDB** | `agentforge-memory-surrealdb` | When agents need graph queries AND a single store. Good fit for cross-agent scenarios. Implements `MemoryStore` + `GraphStore`. |
| **Neo4j** | `agentforge-memory-neo4j` | Heavy graph workloads — multi-hop traversals, shortest path, community detection. Implements `MemoryStore` + `GraphStore`; relational queries on Neo4j are slower than Postgres so we recommend pairing it with another store only when graph is the primary access pattern. |

A backend pairing for the graph-but-also-relational case:

```yaml
# agentforge.yaml — split-store pattern
modules:
  memory:
    driver: postgres                   # primary claim storage
  graph:
    driver: neo4j                      # graph queries only
```

The framework wires both stores; queries hit whichever is appropriate. This is
opt-in; the common case is one store doing both jobs.

### 4.4 Configuration

Standard config schema across drivers, with driver-specific extensions:

```yaml
# agentforge.yaml
modules:
  memory:
    driver: postgres                   # entry-point name
    config:
      dsn: "${POSTGRES_DSN}"
      project: "my-agent"              # used for namespace isolation
      pool:
        min_size: 2
        max_size: 10
      capabilities:                    # explicit opt-in for optional features
        - vector                       # pgvector-backed
```

```yaml
# SurrealDB
modules:
  memory:
    driver: surrealdb
    config:
      url: "ws://localhost:8000/rpc"
      ns: "myorg"
      db: "agents"
      user: "${SURREAL_USER}"
      pass: "${SURREAL_PASS}"
      project: "my-agent"
```

Each driver ships its Pydantic schema; the resolver validates `config:` against it
at agent construction time (P11).

### 4.5 Migrations

Each driver ships its own migration files inside the package:

```
agentforge_memory_postgres/
├── migrations/
│   ├── 0001_init.sql
│   ├── 0002_add_supersedes_index.sql
│   └── 0003_jsonb_gin.sql
├── manifest.yaml
└── ...
```

When `agentforge add module memory-postgres` runs, the manifest copies the
migration files into the agent's `db/migrations/agentforge/` directory with marker
headers. `agentforge db migrate` applies pending migrations using the driver's
native migration runner (Alembic for Postgres/SQLite, native SurrealQL `DEFINE`
for SurrealDB, Cypher migration scripts for Neo4j).

A fresh framework version may add migrations. `agentforge upgrade` updates the
managed migration files; the developer runs `agentforge db migrate` to apply
them. If the developer has run `agentforge fork db/migrations/agentforge/`, the
upgrade skips that directory and the developer is responsible for porting new
migrations themselves — the cost of ownership.

### 4.6 Project namespacing (multi-agent isolation)

Every claim is scoped by `(project, agent)`. The framework auto-fills these from
config; developers do not pass them explicitly. Cross-agent queries are an explicit
opt-in:

```python
# default — sees only this agent's claims
claims = await memory.query(category="finding")

# explicit cross-agent
claims = await memory.query(category="finding", agent=None)  # any agent in this project

# explicit cross-project
claims = await memory.query(category="finding", project=None, agent=None)
```

This is non-negotiable: the default must be safe (own claims only). Cross-scope
access is a deliberate verb.

## 5. Alternatives considered

| Option | Why we didn't pick it |
|---|---|
| One ABC per backend (no unification) | Defeats the swap-without-rewrite goal. Forces every consumer to handle four shapes. |
| Single ABC with all-or-nothing graph support | Forces every driver to ship a graph emulation; the SQLite/Postgres emulations would be slow and lossy. Capability flag is cleaner. |
| Use SQLAlchemy as the underlying engine for relational drivers | Tempting but couples the framework to SQLAlchemy's release schedule and async story. Driver authors can use SQLAlchemy *internally*; we don't expose it. |
| Skip claims abstraction, just expose raw DB clients | Loses cross-agent uniformity (P9). Each agent invents its own schema; no shared tooling possible. |
| Always require Neo4j for graph + Postgres for relational | Most agents need only one of the two; forcing two services for a simple use case is hostile. |

## 6. Migration / rollout

v0.1 ships:

- `agentforge` with `InMemoryStore` as default
- `agentforge-memory-sqlite` (priority — first production deploy needs zero infra)
- `agentforge-memory-postgres` (priority — most common production target)

v0.2 ships:

- `agentforge-memory-surrealdb`
- `agentforge-memory-neo4j`

a predecessor project agents (private, archived) using SQLite or SurrealDB ClaimStore have a direct
migration path because the schema is intentionally compatible — `agentforge migrate
from-legacy-claims` runs and re-keys their data into the new layout.

## 7. Risks

| Risk | Mitigation |
|---|---|
| ABC too narrow — real agents need fields we didn't include | Conformance tests run against real workloads early; the `metadata` JSON field is the escape hatch for module-specific extension |
| Capability flag becomes a footgun (developer assumes graph works on Postgres) | Resolver fails at startup if `agentforge.yaml` references graph operations against a non-graph driver |
| Migration model differs too much across drivers | Standardise the *interface* (`agentforge db migrate`) even though the *engine* differs per driver; conformance test verifies the interface |
| Cross-agent isolation accidentally bypassed | Default queries scope to (project, agent); cross-scope requires `None` — explicit, greppable, code-reviewable |
| Backend SDKs have incompatible async stories (asyncpg vs psycopg vs neo4j-driver) | Drivers internalise this; the ABC is async-only at the contract layer; bridging happens inside the driver, not the consumer |

## 8. Open questions

1. **Vector capability.** Do we ship a vector-search interface in the contract, or
   leave it driver-specific? Lean: leave it driver-specific until two agents need
   it (P12).
2. **Streaming queries — required or capability?** Big query results may not fit
   in memory. Lean: required — every driver implements `stream()`, even if the
   simple drivers stream by paging.
3. **Versioning of the Claim payload schema.** As `Finding` variants evolve, old
   payloads may become unreadable. Need a schema-version field on `Claim` and a
   migration story for stored payloads, separate from DB migrations. Track in a
   follow-up design doc.
4. **DataDog/Snowflake/BigQuery as a cold-storage tier.** Some teams will want to
   archive old claims. Out of scope for v0.x; revisit when an agent runs long
   enough to need it.

## 9. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-09 | One `MemoryStore` ABC + optional `GraphStore` ABC | Unifies the common case without forcing graph emulation on relational backends |
| 2026-05-09 | Four drivers in scope: SQLite, Postgres, SurrealDB, Neo4j | Covers the full matrix: zero-infra / mature relational / mature graph / heavy graph |
| 2026-05-09 | Migrations ship with the driver, applied via `agentforge db migrate` | Versioned and idempotent; every driver follows the same interface even if engines differ |
| 2026-05-09 | Cross-agent isolation default-on, opt-out explicit | Safe by default; cross-scope is a deliberate verb |

## 10. References

- [`architecture.md`](./architecture.md) — where MemoryStore fits
- [`module-system.md`](./module-system.md) — how a memory driver registers and gets configured
- [`design-principles.md`](./design-principles.md) — P1, P5, P8, P11, P12 cited above
- Archived predecessor: `docs/archive/subsystem-memory-layer.md` — a predecessor project's ClaimStore design that this generalises
