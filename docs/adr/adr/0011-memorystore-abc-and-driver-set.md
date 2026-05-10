# ADR-0011: Single MemoryStore ABC + optional GraphStore + four drivers

## Metadata

| Field | Value |
|---|---|
| **Number** | 0011 |
| **Title** | Single MemoryStore ABC + optional GraphStore + four drivers |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, persistence |

---

## 1. Context and problem statement

Production agents need durable claim records (so they can dedupe past
work, reference prior findings, share with sibling agents). Backend
choice is the part of an agent stack most likely to change: prototype
with SQLite, deploy with Postgres, eventually grow into graph-shaped
queries on SurrealDB or Neo4j.

How do we model persistence so that backend swap is a config edit
without rewriting agent business logic, while supporting both
relational claim storage and graph traversal where appropriate?

## 2. Decision drivers

- One agent's "no DB" is another agent's "graph-of-claims"
- Backend swap (sqlite → postgres → surrealdb) must be a config change
- Graph queries are valuable on graph-capable backends; emulating
  graph on SQL backends produces lossy/slow results
- Cross-agent claim sharing requires a shared schema
- Migrations must be coordinated (framework owns schema evolution)

## 3. Considered options

1. **One ABC per backend** — `SqliteStore`, `PostgresStore`, etc., no
   common interface
2. **One unified `MemoryStore` ABC** — every backend implements it;
   graph is a capability flag with emulation where missing
3. **`MemoryStore` ABC + optional `GraphStore` ABC** — relational
   contract for all backends; graph contract only for backends that
   really do graphs
4. **No persistence in framework** — leave it to the agent

## 4. Decision outcome

**Chosen: Option 3 — `MemoryStore` ABC + optional `GraphStore` ABC.**

Every driver implements `MemoryStore` (CRUD over `Claim`s, namespaced
by `(project, agent)`). Drivers that genuinely support graph queries
(SurrealDB, Neo4j) additionally implement `GraphStore` (link, neighbours,
traverse). Drivers that don't (SQLite, Postgres) raise
`CapabilityNotSupported` if asked — surfaced at startup (P11), never
mid-run.

Four drivers in scope: SQLite (zero infra), Postgres (mature relational),
SurrealDB (relational + graph in one), Neo4j (graph-first). Each ships
its migrations; `agentforge db migrate` standardises the operator
interface across drivers.

### Positive consequences

- Backend swap is a config edit + module install
- Graph workloads use real graph backends, not emulations
- Capability flag clearly communicates what each driver supports
- Migrations versioned and idempotent

### Negative consequences (trade-offs)

- Two ABCs to learn (mitigated: most agents only use `MemoryStore`)
- `GraphStore` capability has to be honest — verified at startup
- Four drivers to maintain at conformance level

## 5. Pros and cons of the options

### Option 1: Per-backend ABCs

- − Defeats swap-without-rewrite goal
- − No cross-agent uniformity

### Option 2: Single ABC + emulation

- + One contract
- − Forces every driver to ship a graph emulation; SQLite/Postgres
  emulations would be slow and lossy

### Option 3: `MemoryStore` + optional `GraphStore` (chosen)

- + Honest capability separation
- + Graph backends shine; relational backends stay lean
- − Two ABCs

### Option 4: No persistence

- + Smaller framework
- − Loses cross-agent sharing; loses dedupe; loses idempotency-by-claim

## 6. References

- ADR-0007 (ABC + Protocol surface)
- [`docs/design/persistence-and-orm.md`](../design/persistence-and-orm.md)
- [`docs/features/feat-005-persistence-and-memory.md`](../features/feat-005-persistence-and-memory.md)
- Archived: `docs/archive/subsystem-memory-layer.md`,
  `docs/archive/cr/CR-007*.md`
