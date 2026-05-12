# feat-005: Persistence — `MemoryStore` ABC + drivers

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-005 |
| **Title** | Persistence — unified MemoryStore + drivers (sqlite, postgres, surrealdb, neo4j) |
| **Status** | shipped (Python — `MemoryStore` + sqlite/postgres/neo4j/surrealdb + `VectorStore` + `GraphStore` + RAG; PRs #5/#7/#8 mis-labelled — see §10) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.2 (sqlite, postgres), 0.3 (surrealdb, neo4j) |
| **Languages** | both |
| **Module package(s)** | `agentforge-core` (ABC), `agentforge` (InMemory), `agentforge-memory-sqlite`, `agentforge-memory-postgres`, `agentforge-memory-surrealdb`, `agentforge-memory-neo4j` |
| **Depends on** | feat-001, feat-008 (Finding shape), feat-010 (module system) |
| **Blocks** | none |

---

## 1. Why this feature

A real production agent has to remember things across runs. A code reviewer that
re-flags the same finding on every PR is useless; a research agent that
re-investigates the same hypothesis is wasteful; a triage agent that can't
correlate today's incident with last week's is missing the point. The "remember"
requirement appears the moment an agent goes from demo to production.

The hard part isn't picking a database — it's that databases are the part of
the agent stack most likely to change. A team prototypes with SQLite, deploys
to Postgres, hits graph-shaped queries, considers SurrealDB or Neo4j, then
realises their agent code knows about its persistence layer in 30 places.
Every framework gets this wrong: either no persistence at all (smolagents,
basic Strands), persistence locked to one backend (early CrewAI), or
persistence wrapped so opaquely you can't reason about it (Letta).

## 2. Why it must ship as framework

- **Cross-agent claim sharing requires a shared schema.** If two agents in the
  same team store findings in slightly different shapes, no cross-agent query
  can work. The `Claim` shape and isolation rules must be framework-owned.
- **Migrations have to be coordinated.** When the framework adds a column to
  the claim schema, every agent's database needs to migrate. That requires
  versioned, idempotent migrations shipped with the driver.
- **Backend swap is a one-line change** *only* if the contract is owned by the
  framework. Otherwise it's a rewrite.
- **Cost-cap-and-replay** (don't reprocess the same input) is a framework-level
  feature backed by `MemoryStore`; if persistence is per-agent, each agent
  reinvents idempotency.
- **Without framework ownership:** every agent invents `findings_table.sql`
  with subtle differences, no cross-agent tooling is possible, and migration
  becomes hand-rolled per agent.

## 3. How derived agents benefit

- **Day 1 — zero-config persistence.** `Agent(memory=None)` defaults to
  `InMemoryStore` — runs work, dedupe within a single run works, no infra.
- **Day 7 — first production deploy.** `pip install agentforge-memory-sqlite`,
  add `modules.memory.driver: sqlite` to `agentforge.yaml`, run `agentforge
  db migrate`. Done. One file, no infra.
- **Day 60 — multi-process / multi-worker.** Swap to Postgres: `agentforge swap
  memory sqlite postgres`, set `POSTGRES_DSN`, run migrations. Agent code
  unchanged.
- **Day 120 — graph queries arrive.** `agentforge add module memory-surrealdb`,
  use `await memory.neighbours(claim_id)` in a tool. Existing claim writes
  continue working; the graph capability becomes available.
- **Cross-agent dedupe.** Agent B can query Agent A's claims with explicit
  `agent=None` filter — no schema duplication, no copy-paste.
- **Schema evolution.** The framework adds a `confidence` field in v0.6;
  `agentforge upgrade` ships a migration; the agent's code keeps working
  with the old field set unset.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import Agent, Claim, SimpleFinding
from agentforge_memory_postgres import PostgresMemoryStore   # or string lookup

# String lookup (recommended)
agent = Agent(model="...", tools=[...])   # memory comes from agentforge.yaml

# Or explicit
memory = PostgresMemoryStore(dsn="postgresql+asyncpg://...", project="my-agent")
agent = Agent(model="...", tools=[...], memory=memory)

# Inside a tool, persisting a finding
async def review_pr(pr_url: str) -> dict:
    finding = SimpleFinding(severity="warning", category="style",
                            message="Variable name unclear", file="src/x.py", line=42)
    claim_id = await agent.memory.put(Claim.from_finding(finding, agent="pr-reviewer"))
    return {"claim_id": claim_id}

# Querying across runs
async def already_flagged(file: str, line: int) -> bool:
    prior = await agent.memory.query(category="finding", limit=100)
    return any(c.payload["file"] == file and c.payload["line"] == line for c in prior)
```

### 4.2 Public API / contract

See [`persistence-and-orm.md`](../design/persistence-and-orm.md) §4.2 for the
full `MemoryStore` and `GraphStore` ABC. Summary:

```python
class MemoryStore(ABC):
    async def put(self, claim: Claim) -> str: ...
    async def get(self, claim_id: str) -> Claim | None: ...
    async def query(self, *, project=None, agent=None, category=None,
                    run_id=None, limit=100) -> list[Claim]: ...
    async def supersede(self, old_id: str, new_claim: Claim) -> str: ...
    async def stream(self, **filters) -> AsyncIterator[Claim]: ...
    async def close(self) -> None: ...
    def capabilities(self) -> set[str]: return set()

class GraphStore(ABC):
    async def link(self, source_id, target_id, kind: str, **metadata) -> None: ...
    async def neighbours(self, claim_id, *, kind=None, depth=1) -> list[Claim]: ...
    async def traverse(self, claim_id, query: GraphQuery) -> list[Claim]: ...

class Claim(BaseModel):
    id: str            # ULID
    run_id: str
    project: str
    agent: str
    category: str
    payload: dict[str, Any]
    supersedes: str | None
    created_at: datetime
    metadata: dict[str, Any]
```

### 4.3 Internal mechanics

- Each driver internalises the SDK / ORM choice (asyncpg, surrealdb-py,
  neo4j-async-driver, aiosqlite). Framework only sees the contract.
- `Claim.id` generated framework-side as ULID for monotonic sort + global
  uniqueness.
- `(project, agent)` namespacing applied at every query unless explicitly
  overridden — defaults to the agent's own scope.
- Capability set declared per driver: `{"graph"}` for SurrealDB/Neo4j,
  `{"vector"}` if pgvector enabled, `{"fts"}` for full-text search where
  supported.

### 4.4 Module packaging

| Package | Driver | `MemoryStore` | `GraphStore` |
|---|---|---|---|
| `agentforge` (built-in) | InMemory | yes | no |
| `agentforge-memory-sqlite` | aiosqlite | yes | no |
| `agentforge-memory-postgres` | asyncpg + JSONB | yes | optional via recursive CTE |
| `agentforge-memory-surrealdb` | surrealdb-py | yes | yes |
| `agentforge-memory-neo4j` | neo4j-async | yes | yes |

Each ships migrations, manifest, Pydantic config schema.

### 4.5 Configuration

```yaml
modules:
  memory:
    driver: postgres
    config:
      dsn: "${POSTGRES_DSN}"
      project: "my-agent"
      pool:
        min_size: 2
        max_size: 10

  graph:                  # optional, separate from memory
    driver: neo4j
    config:
      uri: "bolt://localhost:7687"
      auth: ["neo4j", "${NEO4J_PASSWORD}"]
```

## 5. Plug-and-play & upgrade story

`agentforge add module memory-postgres` writes manifest-driven boilerplate:
migration files into `db/migrations/agentforge/`, env-var entries into
`.env.example`, `modules.memory` block into `agentforge.yaml`. Developer runs
`agentforge db migrate`. Done.

`agentforge swap memory sqlite postgres` flips the driver name in config and
runs the new driver's migrations; data migration is a separate one-shot script
the developer runs manually.

`agentforge upgrade` brings in new migration files when the framework adds a
column. Developer runs `agentforge db migrate` post-upgrade.

## 6. Cross-language parity

ABC and `Claim` shape identical. Drivers ship in both languages where
ecosystems support them; sqlite + postgres in both at v0.2; surrealdb in both
at v0.3; neo4j Python first, TS at v0.4 (driver maturity differs).

## 7. Test strategy

- **Conformance suite:** `tests/memory_conformance.py` — every driver passes
  the same 30+ tests (CRUD, supersession, namespacing, streaming, capability
  honesty).
- **Integration:** real DB instances in CI (Postgres via Docker, SurrealDB via
  embedded mode, Neo4j via testcontainers).
- **Migration tests:** apply forward, apply backward (where supported), assert
  schema state.
- **Cross-driver consistency:** the same test data produces the same query
  results across drivers (modulo capability differences).

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Driver ecosystem maturity (Neo4j async TS) | Track per-language status; defer when an SDK isn't ready |
| Schema drift between drivers | Conformance suite covers the contract; driver-specific extensions live in `metadata` |
| Migration ordering across modules | Each module has its own migration prefix (`agentforge_memory_postgres_0001`); `agentforge db migrate` applies them in module-declaration order |
| Should we ship a vector-search capability in v0.x? | Defer; capability flag `"vector"` reserved; require two consumers (P12) before adding to contract |
| Cross-store transactions | Out of goals; document |
| Backup/restore | Driver-specific; runbook per driver, not framework concern |

## 9. Out of scope

- General-purpose ORM. We store claims, not arbitrary user tables.
- Cross-backend transactions or eventual-consistency replication.
- Vector embeddings as a first-class primitive (defer until concrete need).
- A "memory consolidation" / summarisation layer (Letta-style). Build on top
  of the claim store via a tool if needed.

## 10. References

- [`persistence-and-orm.md`](../design/persistence-and-orm.md) — full design
- [`module-system.md`](../design/module-system.md) — how memory drivers register
- [`design-principles.md`](../design/design-principles.md) — P1, P5, P11, P12
- feat-001 (`Agent.memory` consumes), feat-008 (Finding → Claim payload),
  feat-010 (resolver), feat-011 (migration scaffolding)
- Archived: `docs/archive/cr/CR-007*.md`, `docs/archive/subsystem-memory-layer.md`

---

## Implementation status

**Status: shipped (Python). TypeScript port pending.**

The Python implementation landed across three PRs against
`Scaffoldic/agentforge-py`. Each PR was authored against a *shipped
feature number* that does not match this canonical feat-005 ID — the
divergence was not caught until after all three merged. Going forward
every PR uses the canonical number; this addendum maps the shipped
labels back so future archaeology is straightforward.

| Shipped label | Canonical | PR | Branch | Scope delivered |
|---|---|---|---|---|
| feat-007 | feat-005 (sqlite + RAG) | [#5](https://github.com/Scaffoldic/agentforge-py/pull/5) | `feat/007-memory-and-rag` | `MemoryStore` ABC contract was already shipped under feat-001; this PR added `VectorStore` ABC + value types, `run_vector_conformance` suite, `InMemoryVectorStore`, `Retriever` adapter, `Agent(retriever=...)` kwarg + `RuntimeContext.retriever`, and the `agentforge-memory-sqlite` package (`SqliteMemoryStore` + `SqliteVectorStore` over aiosqlite, vectors as float64 BLOBs). |
| feat-009 | feat-005 (graph + neo4j + surrealdb) | [#7](https://github.com/Scaffoldic/agentforge-py/pull/7) | `feat/009-graph-store` | New `GraphStore` ABC + value types (`GraphNode`, `GraphEdge`, `GraphSegment`, `GraphPattern`, `Path`), `run_graph_conformance` suite, `InMemoryGraphStore`, `Agent(graph_store=...)` kwarg + `RuntimeContext.graph_store`, plus two driver packages: `agentforge-memory-neo4j` (`Neo4jGraphStore` + `Neo4jMemoryStore` via the official async neo4j driver) and `agentforge-memory-surrealdb` (`SurrealGraphStore` + `SurrealVectorStore` + `SurrealMemoryStore` — tri-modal). |
| feat-008 | feat-005 (postgres) | [#8](https://github.com/Scaffoldic/agentforge-py/pull/8) | `feat/008-postgres` | `agentforge-memory-postgres` package: `PostgresMemoryStore` + `PostgresVectorStore` over asyncpg + pgvector with HNSW index. |

### Deviations from this spec

- **`VectorStore` and `GraphStore` ABCs were added** as separate
  locked contracts. This spec only mentions `MemoryStore`; the
  shipped `VectorStore` (cosine search, normalised `[0, 1]` scores)
  and `GraphStore` (multi-hop traversal, pattern match) were
  introduced because their shapes don't unify with `MemoryStore` —
  one ABC per concern, not one per backend. Adding new locked
  contracts is a major version event under ADR-0007; both are
  pinned at v0.1.
- **Schema migrations framework deferred.** The spec calls for a
  versioned, idempotent migration runner. v0.1 ships per-driver
  `init_schema()` (idempotent `CREATE TABLE / EXTENSION / INDEX IF
  NOT EXISTS`) only. A real migration framework lands alongside
  the first v0.1.0 → v0.2.0 schema delta. Tracked in roadmap
  backlog.
- **No CLI `db migrate` yet.** Drivers expose `await
  store.init_schema()` directly. CLI integration follows the eventual
  migrations framework.
- **Driver-specific extras:**
  - SurrealDB ships a third capability — `GraphStore` — alongside
    `MemoryStore` and `VectorStore` (genuinely tri-modal).
  - Neo4j ships `MemoryStore` + `GraphStore` (no vector). Vector
    indexing in Neo4j 5.x is a separate follow-up.
  - All non-sqlite drivers wrap an internal `Runner` protocol so unit
    tests inject a fake (no live DB needed in CI). Live integration
    tests are env-gated (`RUN_LIVE_NEO4J`, `RUN_LIVE_SURREAL`,
    `RUN_LIVE_POSTGRES`) with shipped docker-compose dev stacks.

### Pre-commit / CI gate

All three PRs went through the full local gate before push:
`ruff format` + `ruff check` + `mypy --strict` + `bandit` + `pytest
unit + integration (excludes live)` + coverage ≥ 90%. CI mirrors the
gate; pre-commit and CI extend in lockstep when a new package lands
(extending one without the other is a documented drift trap that
caused one CI failure during feat-005 work — see PR #7 commit
`2e90bae`).

### What's *not* yet implemented

- TypeScript port of the entire feat-005 surface.
- Migration framework + CLI command (`agentforge db migrate`).
- Server-side embedding via Postgres (`embeddings.postgres` entry-point
  was reserved but not implemented; the package is pure persistence
  for now).
- Cross-backend tooling (`agentforge swap` for in-place backend
  changes).

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented "how do I…" content. This is the canonical
home for the feature's runbook; feat-011 / feat-019 consume these
sections into scaffolded agent projects.

### How do I pick a backend?

| Constraint | Backend |
|---|---|
| Single host, no extra deps, durable across restarts | `agentforge-memory-sqlite` |
| Production scale, multi-writer, managed (RDS/Neon/Supabase) | `agentforge-memory-postgres` |
| Graph relationships first-class, mature ecosystem | `agentforge-memory-neo4j` |
| Tri-modal (claims + vectors + graph) in a single store | `agentforge-memory-surrealdb` |
| Ephemeral / unit tests | `InMemoryStore` (built into `agentforge`) — the default when `memory=` is omitted |

Install the package, then construct via the driver's async factory.

### How do I add SQLite persistence to a single-host agent?

```python
from agentforge import Agent
from agentforge_memory_sqlite import SqliteMemoryStore

memory = await SqliteMemoryStore.from_path("./agent.db")
await memory.init_schema()

async with Agent(model="bedrock:...", memory=memory) as agent:
    result = await agent.run("…")
```

`init_schema()` is idempotent — safe to call on every startup. The
schema is `CREATE TABLE IF NOT EXISTS …` plus indices.

### How do I add Postgres for production scale?

```python
from agentforge_memory_postgres import PostgresMemoryStore, PostgresVectorStore

memory = await PostgresMemoryStore.from_dsn(
    "postgresql://postgres:postgres@localhost:5432/agentforge",
    min_size=2,
    max_size=10,
)
await memory.init_schema()

# Optional: vectors alongside on the same DB
vectors = await PostgresVectorStore.from_dsn(POSTGRES_URL, dimensions=1024)
await vectors.init_schema()   # provisions pgvector + HNSW index
```

The pool is sized at construction; defaults
(`min_size=1, max_size=10`) suit most production workloads. Each
method acquires a connection per call and wraps mutations in
`async with conn.transaction()`. Capability `{"transactions"}` is
declared.

### How do I add RAG (vector search) to an agent?

```python
from agentforge import Agent, Retriever
from agentforge_bedrock import BedrockEmbeddingClient
from agentforge_memory_postgres import PostgresVectorStore

embedder = BedrockEmbeddingClient(model_id="amazon.titan-embed-text-v2:0")
vectors = await PostgresVectorStore.from_dsn(POSTGRES_URL, dimensions=1024)
await vectors.init_schema()

retriever = Retriever(store=vectors, embedder=embedder, top_k=5)

agent = Agent(model="bedrock:...", retriever=retriever)
```

The `Retriever` adapter wires `VectorStore.search` to the strategy
context — strategies that consume RAG (ReAct, Plan-Execute) pull
relevant context per step automatically. Cosine similarities are
returned clamped to `[0, 1]` regardless of backend.

### How do I add a graph store?

```python
from agentforge import Agent
from agentforge_memory_neo4j import Neo4jGraphStore, Neo4jMemoryStore

memory = await Neo4jMemoryStore.from_url(
    "bolt://localhost:7687",
    auth=("neo4j", os.environ["NEO4J_PASSWORD"]),
)
graph = await Neo4jGraphStore.from_url(
    "bolt://localhost:7687",
    auth=("neo4j", os.environ["NEO4J_PASSWORD"]),
)

agent = Agent(model="bedrock:...", memory=memory, graph_store=graph)
```

SurrealDB is tri-modal — one connection serves `MemoryStore`,
`VectorStore`, and `GraphStore` (declared capabilities reflect
that intersection). Neo4j ships `MemoryStore` + `GraphStore`
today; vector indexing in Neo4j 5.x is a follow-up.

### How do I namespace claims across projects / agents?

`Claim` carries `project` and `agent` fields; the store filters
all queries to the calling `(project, agent)` by default. Pass
overrides explicitly when you need cross-namespace queries:

```python
claims = await memory.query(project="other-project", agent="other-agent")
```

`Claim.id` is a ULID — monotonic per process, globally unique. Use
`memory.supersede(old_id, new_claim)` to evolve a claim without
losing the audit trail (the old row stays; the new one links via
`supersedes`).

### How do I run integration tests against a real DB?

Each driver ships a `docker-compose.dev.yml` and an env-gated test
file:

```bash
docker compose -f packages/agentforge-memory-postgres/docker-compose.dev.yml up -d
RUN_LIVE_POSTGRES=1 \
  POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/agentforge \
  uv run pytest packages/agentforge-memory-postgres/tests/integration -v
```

Same pattern for Neo4j (`RUN_LIVE_NEO4J=1`) and SurrealDB
(`RUN_LIVE_SURREAL=1`). CI does **not** run live tests; the unit
tests cover every driver via in-process fakes that route SQL /
Cypher / SurrealQL to in-memory backings.

### How do I provision schemas without a real migration framework?

Every driver exposes `await store.init_schema()` — idempotent
`CREATE … IF NOT EXISTS`. Call it once at app startup. A versioned
migration framework + `agentforge db migrate` CLI lands alongside
the first v0.1.0 → v0.2.0 schema delta; the v0.1 backlog tracks
this.

### When should I NOT use a particular backend?

- **SQLite for concurrent writers.** Single-writer; under
  contention you'll see `database is locked` errors. Switch to
  Postgres for any multi-process deployment.
- **Neo4j when you don't need graphs.** Operational overhead is
  high for a key-value claim log. Use Postgres unless graph queries
  are central.
- **SurrealDB for primary persistence on critical data today.**
  The project is young; we ship a driver because it's genuinely
  tri-modal and convenient for prototypes, but Postgres is the
  recommended production default.
- **`InMemoryStore` past a single process.** Lost on restart. Fine
  for unit tests; for a real agent always pass a durable `memory=`.
