# feat-017: CLI runtime

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-017 |
| **Title** | CLI — `agentforge run`, `eval`, `debug`, `db migrate`, `list`, `config`, `status` |
| **Status** | shipped (Python — `run` + `eval` + `debug` + `db {migrate,backup,restore,purge,query}` + `health`) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 (`run` + `eval` + `debug` + `db {migrate,backup,restore,purge,query}` + `health` — all shipped) |
| **Languages** | both |
| **Module package(s)** | `agentforge` |
| **Depends on** | feat-001, feat-005, feat-006, feat-010, feat-012 |
| **Blocks** | none |

---

## 1. Why this feature

A framework's command-line surface is its operational interface. A team
debugging a production agent at 2am needs `agentforge run --replay run-id-X`
to reconstruct the failure, `agentforge debug` to step through, and
`agentforge eval` to assert that a fix doesn't regress.

Without a CLI, every team scripts their own `run.py` with subtly different
arg-parsing, runs evals through bespoke pytest invocations, and debugging
becomes "add print, redeploy, wait." Operations become per-agent folklore
rather than transferable skill.

## 2. Why it must ship as framework

- **Operational uniformity across agents.** A runbook that says "to reproduce
  a failed run, do `agentforge run --replay <run-id>`" applies everywhere.
- **CLI commands depend on framework internals** (loading `Agent`,
  reading `agentforge.yaml`, accessing `MemoryStore`, validating module
  config). Per-agent reimplementation would duplicate framework wiring.
- **Tooling integrations** (CI eval gates, deployment health checks) only
  work if the CLI surface is stable across agents.
- **Without framework ownership:** every agent has its own `Makefile` /
  `run.sh` with different conventions, no transferable skills, no
  shared CI patterns.

## 3. How derived agents benefit

- **Day 1 — `agentforge run "..."` works.** From a fresh scaffold, a single
  command produces output.
- **Day 7 — eval in CI.** `agentforge eval --fixtures ./fixtures/`
  drops into any CI workflow.
- **Day 30 — debug a production failure.** `agentforge run --replay
  run-id-X` reconstructs from logs/claims.
- **Day 90 — DB ops.** `agentforge db migrate`, `agentforge db backup`,
  `agentforge db purge --older-than 30d` — across drivers.
- **Day 180 — health check.** `agentforge status` returns "all modules
  loadable, config valid, DB reachable" — perfect for k8s liveness.

## 4. Feature specifications

### 4.1 User-facing experience

```bash
# Run
agentforge run "Review this PR: https://..."
agentforge run --task-file ./tasks/triage.txt
agentforge run --replay 01HX7K... --to-step 5
agentforge run --override agent.budget.usd=10 "..."

# Eval
agentforge eval --fixtures ./tests/golden.jsonl --threshold 0.8
agentforge eval --fixtures ./tests/golden.jsonl --output-format junit > eval.xml

# Debug — interactive stepper
agentforge debug --replay 01HX7K...
   ↳ opens an REPL: step / inspect state / re-issue tool call

# Modules + config + status
agentforge list modules
agentforge list modules --available
agentforge add module memory-postgres
agentforge swap memory sqlite postgres
agentforge remove module memory-postgres
agentforge config validate
agentforge config show --resolved
agentforge status

# DB
agentforge db migrate
agentforge db backup --to ./backup.tar
agentforge db restore --from ./backup.tar
agentforge db purge --older-than 30d
agentforge db query 'category:finding agent:pr-reviewer'

# Scaffolding (feat-011)
agentforge new my-agent --template code-reviewer
agentforge upgrade
agentforge fork <path>
```

### 4.2 Public API / contract

CLI surface is the API. Every command is locked from the version it ships
in; flags may be added with safe defaults; flags may be deprecated through
one minor cycle.

The CLI is built with Typer (Python) / commander (TS). Both produce
equivalent UX:

```
agentforge --help
agentforge <command> --help
```

Programmatic use:

```python
from agentforge.cli import run_command

await run_command(["run", "--task-file", "./task.txt"])
```

### 4.3 Internal mechanics

- Each command resolves config (feat-012), constructs an `Agent` (feat-001),
  performs its action.
- `agentforge run --replay` reads the persisted run from `MemoryStore`
  (feat-005), reconstructs `AgentState`, replays steps deterministically
  using mocked LLM responses from the recording.
- `agentforge db <subcommand>` dispatches to the active memory driver
  (feat-005). Drivers expose a small `db` method set; not all drivers
  support every subcommand (e.g. `restore` may be no-op for in-memory).
- `agentforge status` runs preflight checks: every module loadable,
  config validates, every backend reachable (with timeouts).

### 4.4 Module packaging

CLI lives in `agentforge`. Subcommands plug in via entry point
`agentforge.cli_subcommands` so modules can extend the CLI (e.g.
`agentforge-otel` could add `agentforge otel test-export`).

### 4.5 Configuration

```yaml
cli:
  default_format: "rich"          # "rich" | "json" | "plain"
  prompt_for_confirmation: true   # for swap/remove/purge
  pager: "auto"
```

## 5. Plug-and-play & upgrade story

CLI surface stable across minor versions. New subcommands ship in minor
bumps. A breaking change requires a major bump and a deprecation cycle.

## 6. Cross-language parity

Both CLIs share the command tree, flag names, and exit codes. Output
formatting is idiomatic per language (Rich on Python, chalk on TS) but
the `--output-format json` produces identical JSON.

## 7. Test strategy

- **End-to-end command tests:** every command invoked against a fixture
  agent; exit code + output asserted.
- **Replay determinism:** running with `--replay` against a recorded run
  produces byte-identical output.
- **Cross-platform:** Linux, macOS, Windows in CI matrix.
- **JSON output stability:** snapshot test for `--output-format json`.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| CLI surface grows unboundedly | Top-level commands frozen at v0.x; new actions become subcommands of existing groups |
| Argument parsing inconsistency between Py and TS | Shared spec file; CI compares help output |
| Long-running commands without progress indication | Rich/chalk progress bars; structured TTY detection; quiet mode for CI |
| CLI subcommand entry-point trust | Same trust model as modules — package authors trusted; loaded from venv |
| Should we expose `agentforge api serve` for HTTP exposure? | Yes — but routed via feat-014 (A2A); CLI command is sugar |

## 9. Out of scope

- A TUI dashboard. Out of scope; CLI emits structured data; build TUI on
  top.
- IDE integrations. Out of scope; LSP / DAP are future work.
- Plugin system for new top-level commands by third parties. Subcommand
  extension via entry points is enough.

## 10. Implementation status (Python)

Shipped in PR #20 against the `agentforge` package — every CLI
subcommand the spec lists, plus the persistence + replay
foundations they needed.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `34ffd7f` | `MemoryStore.delete()` on the ABC + every driver (in-memory, sqlite, postgres, neo4j, surrealdb) + conformance suite + `RecordRunHook` + `Agent(record_runs=)` |
| 2 | `c80f54f` | `ReplayLLMClient.from_recording(memory, run_id)` + `replay_tools(...)` + `ReplayExhausted` |
| 3 | `1eeb6fb` | `build_agent_from_config(config)` + `load_and_build(...)` resolving providers / memory / evaluators / strategy / tools via the global Resolver |
| 4 | `5e6fc7a` | `agentforge run` CLI: positional or `--task-file`, `--override`, `--output-format {rich,json,plain}`, `--replay`, `--to-step`, `--record`, exit codes 0/1/2/3/4 |
| 5 | `b5aebbc` | `agentforge eval --fixtures JSONL --threshold` with `--output-format {rich,json,junit}`, exit 5 on threshold fail |
| 6 | `44e1f86` | `agentforge debug --replay RUN_ID` stdlib `cmd.Cmd` REPL with `step` / `back` / `state` / `inspect FIELD` / `steps` / `quit` |
| 7 | `f4d8b9b` | `agentforge db {migrate,backup,restore,purge,query}` with JSONL backup/restore round-trip and a tiny `category:X agent:Y` query DSL |
| 8 | `98e4c85` | `agentforge health` preflight (config valid + Resolver walk + backend reachability) |
| 9 | (this PR) | Spec status + Implementation section + Runbook + roadmap + CHANGELOG + state files |

### Deviations from the design

- **`agentforge status` (spec §4.1, §4.2) → `agentforge health`.**
  feat-011 already shipped `agentforge status` for scaffolding
  state. Renaming the preflight command to `health` keeps the
  shipped command's contract intact.
- **argparse instead of Typer / commander (spec §4.2).** The
  existing CLI uses argparse (feat-010/011/012); no new
  dependency added. The contract — command names, flags, exit
  codes — is unchanged.
- **Templates ship in-wheel.** Inherited from feat-011 (templates
  module ships inside the `agentforge` wheel via hatchling
  force-include). No separate `agentforge-templates` repo.
- **`db migrate` is a no-op on driverless schemas.**
  `InMemoryStore` has no schema; `SqliteMemoryStore` creates
  schema eagerly in `from_path`. Both print an info message and
  exit 0. Postgres / Neo4j / SurrealDB call their respective
  `init_schema()`.
- **`unfork` partial restore is documented in feat-011 §10** and
  remains unchanged here.

### Reserved categories (on-disk contract)

- `__step` — one claim per emitted `Step` (recorded when
  `record_runs` set).
- `__eval` — one claim per `EvalResult` after the loop.
- `__run` — one claim per run summary (output, cost, tokens,
  duration, finish_reason).

`ReplayLLMClient.from_recording` consumes `__step`; `agentforge
debug --replay` consumes `__step`; `agentforge db query` /
`backup` work on every category including these.

### Exit codes (locked)

| Code | Meaning | Surfaced by |
|---|---|---|
| 0 | success | every command |
| 1 | generic error | run / eval / debug / db / health |
| 2 | config invalid (Pydantic ValidationError or ModuleError during load) | run / eval / health |
| 3 | budget exceeded | run |
| 4 | guardrail tripped | run |
| 5 | eval threshold not met | eval |

### Not implemented (deferred)

- **TypeScript engine (spec §6).** Out of scope; the Python
  implementation defines the on-disk contract the TS engine will
  mirror.
- **`agentforge run --run-tests` (spec §4.1).** Surfaced as an
  open question in §8; deferred until the test-runner integration
  (post-feat-019) lands.
- **CI matrix for `--replay` across prior versions (spec §7).**
  No prior versions to upgrade from yet.
- **Windows CI matrix (spec §7).** Existing CI is Linux + macOS;
  Windows lands when there's a Windows-shaped consumer asking.
- **Subcommand extension entry-point (spec §4.4).** Entry-point
  category `agentforge.cli_subcommands` not wired yet; the
  framework's own subcommands are registered explicitly in
  `cli/main.py`.

## 11. Runbook

### Run an agent

```bash
agentforge run "Review this PR" --output-format json
agentforge run --task-file ./task.txt
agentforge run --override agent.budget.usd=10 "..."
```

Exit codes: 0 success / 2 config invalid / 3 budget exceeded /
4 guardrail / 1 other error.

### Replay a recorded run

```bash
# 1. Configure modules.memory so the run can be persisted.
# 2. Run with --record:
agentforge run --record "..."

# 3. Replay (the loop reads recorded LLMResponse + tool obs):
agentforge run --replay 01HX...
```

Determinism: same recorded run + name-matched tools + same task
→ byte-identical `RunResult.steps`.

### Evaluate against fixtures

```bash
agentforge eval --fixtures ./tests/golden.jsonl --threshold 0.8
agentforge eval --fixtures ./tests/golden.jsonl \
  --output-format junit > eval.xml
```

Fixture JSONL: `{"task": "...", "expected": "...", "metadata": {}}`.
Exit 5 when mean score < threshold; 0 otherwise.

### Step through a recorded run

```bash
agentforge debug --replay 01HX...
> step          # advance to next emitted step
> state         # print the full payload
> inspect tool_call.name
> steps         # list every step with kind + iteration
> quit
```

### Database ops

```bash
agentforge db migrate                          # init_schema if present
agentforge db backup --to /tmp/dump.jsonl     # JSONL stream of every claim
agentforge db restore --from /tmp/dump.jsonl  # bulk put()
agentforge db purge --older-than 30d --yes
agentforge db purge --run-id 01HX... --yes
agentforge db query 'category:finding agent:pr-reviewer' --limit 50
```

### Preflight (health)

```bash
agentforge health
agentforge health --output-format json
```

Exit 0 if every check passed, 1 if any FAIL, 2 if the config
didn't validate.

### Naming note

- `agentforge status` (feat-011) — scaffolding file state.
- `agentforge health` (feat-017) — operational preflight.

## 12. References

- feat-001, feat-005, feat-006, feat-010, feat-011, feat-012
- Typer: https://typer.tiangolo.com
- commander: https://github.com/tj/commander.js
