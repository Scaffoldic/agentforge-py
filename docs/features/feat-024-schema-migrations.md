# feat-024: Schema migrations framework

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-024 |
| **Title** | Schema migrations framework — versioned migrations + checksum tracking across all four persistent stores |
| **Status** | shipped (Python) |
| **Owner** | kjoshi |
| **Created** | 2026-05-14 |
| **Target version** | 0.2 |
| **Languages** | both (TS deferred to v0.4) |
| **Module package(s)** | `agentforge-core` (Migration value + Migrator Protocol + discovery helpers), `agentforge` (CLI extension), `agentforge-memory-postgres` / `-sqlite` / `-neo4j` / `-surrealdb` (per-driver implementations) |
| **Depends on** | feat-005 (MemoryStore / VectorStore / GraphStore + persistent drivers) |
| **Blocks** | none |

---

## 1. Why this feature

Every persistent-store driver today bundles a single
monolithic `init_schema()` blob that runs a series of
`CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ... ADD COLUMN
IF NOT EXISTS` / `DEFINE TABLE IF NOT EXISTS` /
`CREATE CONSTRAINT IF NOT EXISTS` statements. For a fresh
install that works. For an *upgrade*, the idempotent
`IF NOT EXISTS` predicates carry the schema delta —
implicitly, opaquely, and brittly:

- **No audit trail.** Operators can't tell which delta
  was applied when, or whether a partial run got
  interrupted.
- **No checksum.** A migration file edited after deploy
  silently diverges; nothing detects it.
- **No ordering guarantee.** Squeezing each schema delta
  into an idempotent statement constrains what the
  schema can express (no destructive renames, no data
  backfills with rollback).
- **The feat-022 upgrade was the canary.** Adding
  `embedding_tsv tsvector` to the Postgres `vectors`
  table only worked because the column happened to be
  addable via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
  The next non-additive schema change would break this
  pattern.

feat-024 ships a real, versioned migration framework
across all four persistent-store drivers so v0.2.0 →
v0.3.0 schema deltas have a clean home.

## 2. Why it must ship as framework

- **Schema migrations are framework infrastructure.**
  Every driver author should not reinvent versioning,
  checksum tracking, and applied-state recording.
- **Cross-driver consistency.** A consistent `Migrator`
  Protocol (`apply_pending` / `status` /
  `current_version`) means operators learn one tool,
  apply it to any backing store.
- **The `agentforge db migrate` CLI is the user-facing
  surface.** It needs a stable contract for "what does
  the configured driver expose?" — that's the Protocol.
- **Without framework ownership:** every agent ships
  bespoke migration logic; backups, restores, and
  upgrades become per-driver lore.

## 3. How derived agents benefit

A scaffolded agent's deployment flow becomes:

```bash
# Fresh install
agentforge db migrate          # applies 0000/0001/...

# After upgrading agentforge
agentforge db migrate-status   # lists pending migrations
agentforge db migrate          # applies just the pending ones
```

No code changes. The driver itself ships the migration
files in-package; upgrading the driver package brings the
new migrations with it.

## 4. Feature specifications

### 4.1 User-facing experience

- `agentforge db migrate` — applies all pending migrations
  for the configured store. Idempotent: re-running after a
  successful run is a no-op.
- `agentforge db migrate-status` — lists applied + pending
  migrations per configured store with checksum-match
  indicator.
- Drivers expose `migrator() -> Migrator` returning a
  configured instance pointing at the package's
  in-bundle `migrations/` directory.
- `init_schema()` keeps working on every driver — it
  delegates to `self.migrator().apply_pending()` so
  existing callers (tests, the old CLI fallback path)
  don't break. Deprecation warning emitted; removal
  deferred to v0.3.

### 4.2 Public API / contract

**`Migration`** — new frozen Pydantic value at
`agentforge_core.contracts.migrator`:

```python
class Migration(BaseModel):
    """One versioned schema migration."""

    model_config = ConfigDict(frozen=True, strict=True)

    id: str           # 4-digit prefix, e.g. "0001"
    name: str         # snake_case description
    up: str           # SQL / Cypher / SurrealQL body
    checksum: str     # SHA-256 over LF-normalised up
```

**`MigrationStatus`** — value reporting per-migration
state for `Migrator.status()`:

```python
class MigrationStatus(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    migration: Migration
    applied: bool
    applied_at: datetime | None
    checksum_match: bool   # True when applied and recorded
                           # checksum equals file checksum
```

**`Migrator`** — runtime Protocol at
`agentforge_core.contracts.migrator`:

```python
class Migrator(Protocol):
    async def apply_pending(self) -> list[Migration]: ...
    async def status(self) -> list[MigrationStatus]: ...
    async def current_version(self) -> str | None: ...
```

**`MigrationChecksumError`** — raised when an applied
migration's recorded checksum no longer matches the
file's checksum. Subclass of `ModuleError`.

**`discover_migrations(path, *, suffix)`** — module-level
helper at `agentforge_core.migrations.discover`. Globs
`NNNN_*.suffix` in `path`, parses id + name from each
filename, hashes contents, returns `list[Migration]`
sorted by id ascending.

**Per-driver `migrator()` method** on every persistent
store class. Returns a `Migrator` configured against the
package's migrations directory.

### 4.3 Internal mechanics

**Filesystem discovery.** Each driver package ships its
migrations at
`<package>/migrations/NNNN_<snake_name>.<ext>` where
`<ext>` is `sql` for Postgres/SQLite, `cypher` for Neo4j,
`surql` for SurrealDB. `discover_migrations` lists the
directory, filters by suffix, parses the integer prefix,
sorts ascending. The first migration is always
`0000_migrations_table.<ext>` which bootstraps the
tracking table.

**Tracking state.** Postgres / SQLite / SurrealDB use an
`agentforge_migrations` table with columns
`(id TEXT PK, name TEXT, checksum TEXT, applied_at TIMESTAMP)`.
Neo4j uses an `:AgentforgeMigration` node label with the
same properties. The tracking table itself is created by
`0000_migrations_table`.

**Apply order.** `apply_pending`:
1. Calls `current_version()` to find the highest applied
   id (or `None` if tracking table doesn't exist yet).
2. For each migration from `current_version + 1` to the
   end of the discovered list:
   a. Opens a transaction (where supported).
   b. Executes the migration's `up` body.
   c. Inserts the tracking row with the file's checksum.
   d. Commits.
3. Returns the list of applied migrations.

**Checksum verification.** Every `apply_pending` and
`status` call cross-checks the stored checksum against
the on-disk file. Mismatch raises
`MigrationChecksumError` — we do NOT silently re-apply.

**Atomicity per driver:**
- **Postgres:** explicit `BEGIN; ... COMMIT;` per
  migration. Failed migrations roll back cleanly.
- **SQLite:** `BEGIN; <executescript body>; COMMIT;`.
  Note SQLite DDL is transactional, so this is safe.
- **Neo4j:** one Cypher transaction per migration via the
  async driver's `session.execute_write` helper.
- **SurrealDB:** per-statement; SurrealDB v1.x doesn't
  expose multi-statement transactions. Documented in the
  runbook.

### 4.4 Module packaging

- **Core framework** (`Migration` / `Migrator` /
  `discover_migrations` / `MigrationChecksumError`)
  ships in `agentforge-core` (zero new deps).
- **Per-driver migrators + migration files** ship inside
  each existing driver package — no new sister packages.
- **CLI extension** lives in
  `agentforge.cli.db_cmd` (existing module).

### 4.5 Configuration

Nothing new in `agentforge.yaml`. Migration files live
in-package; their location is hard-coded relative to the
driver's `__file__`. The `agentforge db migrate` CLI
reads the configured `modules.memory` driver to decide
which migrator to invoke.

## 5. Plug-and-play & upgrade story

- Existing deployments call `init_schema()` once after
  install. After upgrading to a version with feat-024,
  the *first* `init_schema()` call:
  - Notices no `agentforge_migrations` table exists.
  - Applies `0000_migrations_table` to create it.
  - Applies `0001_initial` which is a no-op against an
    existing schema (every statement uses
    `IF NOT EXISTS`).
  - Records both as applied.
- Subsequent upgrades add `0002_*`, `0003_*` migrations.
  Operators run `agentforge db migrate` to apply them.
- The `init_schema()` deprecation warning lands in v0.2
  release notes; removal in v0.3.

## 6. Cross-language parity

TypeScript port deferred to v0.4. The migration format
(filename convention, tracking schema, checksum
algorithm) is language-neutral; the TS port can read the
same migration files and write to the same tracking
table.

## 7. Test strategy

- **Core framework unit tests** — `discover_migrations`
  ordering + filtering; checksum determinism +
  line-ending normalisation; `Migration` value
  validation.
- **Per-driver unit tests** — empty store →
  `apply_pending()` applies every migration in order;
  re-running is a no-op; checksum mismatch raises;
  `status()` returns correct applied flags.
- **Per-driver live tests** (gated) — runs
  `apply_pending` against a real backing store; asserts
  the tracking table + schema invariants survived.
- **CLI smoke test** — `agentforge db migrate` +
  `migrate-status` against a configured store.

## 8. Risks & open questions

- **Production rollback.** v0.2 has no `down` migrations.
  Operators rolling back a deployment must restore from
  backup. Documented; v0.3 will add a `down` slot.
- **Concurrent migrate calls.** Two concurrent
  `apply_pending` invocations could race on the tracking
  table. Postgres/SQLite serialise via transactions;
  Neo4j via session locking. SurrealDB v1.x doesn't —
  documented; production deployments should single-flight
  the migrate call.
- **Checksum drift in dev.** Devs editing a migration
  file post-apply trigger `MigrationChecksumError`.
  Documented in the runbook — re-roll from scratch in
  dev (`DROP TABLE agentforge_migrations`) or add a new
  migration.

## 9. Out of scope

- `down` migrations (rollback) — v0.3 spec.
- Migration squashing / consolidation utilities — when
  the migration list grows long.
- Pluggable migrator backends — no resolver category in
  v0.2.
- Auto-generation of migrations from schema
  introspection.
- TypeScript port (v0.4).

## 10. References

- Alembic (SQLAlchemy) — Python migration tool;
  influences the per-file `NNNN_name` filename
  convention.
- Flyway / Liquibase — Java migration tools;
  influences the SHA-256 checksum + tracking-table
  pattern.
- Rails ActiveRecord migrations — influences the
  per-driver SQL dialect approach.

## 11. Implementation status (Python)

**Status: shipped (Python).** Landed as a single PR per
the user's "Spec + framework + all four drivers" scope
choice. Chunked across 7 commits:

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `126cb67` | This spec + catalogue row + roadmap pointer. |
| 2 | `3ac96b1` | `Migration` value + `Migrator` Protocol + `discover_migrations` + `MigrationChecksumError` + 18 unit tests in `agentforge-core`. |
| 3 | `e501788` | `PostgresMigrator` + 2 migration files (`0000_migrations_table` + `0001_initial` — claims schema; the vectors table stays under the dim-parameterized `init_schema`) + `init_schema()` shim + unit + live tests. |
| 4 | `f537d1c` | `SqliteMigrator` + 3 migration files (`0000` + `0001_initial` + `0002_fts5`) + `from_path` rewritten to bootstrap via the migrator + 5 unit tests. |
| 5 | `0784244` | `Neo4jMigrator` + 2 Cypher migration files + `:AgentforgeMigration` tracking node + statement-splitting helper for Neo4j 5.x's one-statement-per-`run()` rule + 4 unit tests. |
| 6 | `8e169cf` | `SurrealMigrator` + 2 SurrealQL migration files + `agentforge_migrations` tracking table + 3 unit tests. SurrealVectorStore's `init_schema()` retains the dim-parameterized DDL. |
| 7 | this commit | `agentforge db migrate` routes through the framework when `memory.migrator()` exists (falls back to legacy `init_schema()` otherwise) + new `agentforge db migrate-status` subcommand + spec status flip + catalogue + roadmap + CHANGELOG + state. |

### Out-of-scope (deferred)

- `down` migrations — v0.3.
- Migration squashing — when the list grows long.
- TypeScript port — v0.4.

### v0.3 polish — parameterized migrations (Postgres + SurrealDB vectors)

Closes the deferred dim-parameterized item from the v0.2
ship. Migration bodies now support `${var}` placeholders
via Python's `string.Template` semantics; per-driver
migrator constructors gain an optional `variables:
dict[str, str]` kwarg. Checksums are computed over the
un-substituted template body — re-deploying with a
different value (e.g. swapping a 768-dim embedder for
1536) produces the same checksum, so drift detection
stays correct.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `ce3141a` | `render_migration_up(body, variables)` helper at `agentforge_core/migrations/template.py`. Uses `safe_substitute` so unknown placeholders pass through (template-key typos surface as apply-time SQL errors). Re-exported via `agentforge_core.migrations`. 6 new unit tests covering substitution, `$$` escape, and checksum-over-template invariant. |
| 2 | `a25193a` | `PostgresMigrator` / `SqliteMigrator` / `Neo4jMigrator` / `SurrealMigrator` constructors all gain optional `variables=` kwarg. Postgres + SurrealDB get per-store migration subdirectories: vector migrations move to `migrations/vector/0100_vectors.{sql,surql}` (id range 0100-0199 to avoid colliding with memory's 0001). `PostgresVectorStore.migrator()` and `SurrealVectorStore.migrator()` pre-configure with `variables={"dimensions": str(self._dim)}` + the vector subdir path. `_build_init_schema_sql` / `_build_init_schema` helpers removed; `init_schema()` on both vector stores delegates to the migration framework. SQLite + Neo4j migrators get the same passthrough kwarg for future-proofing (no functional change today). |
| 3 | this commit | Spec subsection + catalogue + roadmap flip + CHANGELOG + state. |

The dim parameter is the only one in v0.2. Future
follow-ups can use the same mechanism for embedding
provider names, custom table prefixes, or per-tenant
schema namespacing.

## 12. Runbook

Audience: agent developers + operators upgrading deployments.

### How do I add a migration?

1. Create a new file in the driver's `migrations/`
   directory: `<package>/migrations/NNNN_<snake_name>.<ext>`
   where `NNNN` is the next 4-digit id and `<ext>`
   matches the driver (`sql` / `cypher` / `surql`).
2. Write the up-statement(s). Idempotency is NOT required
   — the framework only applies the migration once.
3. Run `agentforge db migrate` locally to apply it.
4. Commit the file. CI will apply it on the next deploy.

### How do I check migration status?

```bash
agentforge db migrate-status
```

Lists every discovered migration with applied/pending
flag + checksum-match indicator. Use `--path agentforge.yaml`
to point at a non-default config.

### How do I upgrade an existing deployment?

After upgrading the `agentforge` package:

```bash
agentforge db migrate
```

Idempotent: only pending migrations are applied. The
first time you run it post-upgrade, the framework
notices the missing `agentforge_migrations` table,
creates it, and marks all bundled migrations as applied
(the initial `0001_initial` is a no-op against an
existing schema thanks to `IF NOT EXISTS` predicates).

### What if I get `MigrationChecksumError`?

A migration file was edited after being applied. Options:

- **Dev environment:** drop the `agentforge_migrations`
  table (or the `:AgentforgeMigration` nodes for Neo4j)
  and re-run `migrate`. Migrations re-apply from
  scratch.
- **Production:** restore the original migration file
  contents from git, OR add a new migration that
  expresses the intended delta.

Never bypass the checksum check in production.

### Can I roll back a migration?

Not in v0.2. v0.3 will add a `down` slot. For now,
restore from backup or add a forward-migration that
reverses the change.

### When should I NOT use the migration framework?

- Pure read-only workloads (no schema bootstrap needed).
- Test fixtures that drop + recreate state per run —
  `init_schema()` is faster than going through the
  framework's tracking-table writes.
