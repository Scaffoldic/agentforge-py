# feat-028: Durable execution + human-in-the-loop

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-028 |
| **Title** | Durable execution (checkpoint-and-resume) + human-in-the-loop approval gates |
| **Status** | proposed |
| **Owner** | kjoshi |
| **Created** | 2026-06-22 |
| **Target version** | 0.5 (spec written on the 0.4 train; build 0.5/0.6) |
| **Languages** | `python` (TS deferred) |
| **Module package(s)** | `agentforge-core` (contracts + values), `agentforge` (strategy/agent wiring); a checkpoint driver package per backend (sqlite first) |
| **Depends on** | feat-001 (`Agent`), feat-002 (strategies), feat-007 (`BudgetPolicy` / `RunContext`), feat-005 (`MemoryStore` substrate), feat-017 (recording/replay seam), feat-012/026 (config) |
| **Blocks** | the governance spine's audit story (HITL approvals are audit events) |

---

## 1. Why this feature

A production agent run is a multi-step, expensive, side-effecting process. Two
things every serious deployment eventually needs, and which agentforge-py
cannot do today:

1. **Durable execution** — a run survives process death. If the process
   crashes, is redeployed, or times out at step 7 of 12, the run **resumes at
   step 7** instead of restarting, never re-paying for completed LLM calls or
   re-firing side-effecting tool calls.
2. **Human-in-the-loop (HITL)** — a run can **pause** before an irreversible
   action (apply a patch, issue a refund, send outbound comms, deploy),
   persist its full state, hand control back to a human, and **resume later —
   possibly in a different process, hours later** — once the human approves or
   edits.

These are one capability: you cannot suspend-and-resume-across-time without
durable state. Today `Agent.run` executes the entire reasoning loop inside a
single `await self._strategy.run(state)` — if that coroutine dies, the run is
gone, and there is no interception point to pause it for approval.

This is precisely the control-plane capability the managed platforms charge
for (Bedrock AgentCore, Temporal Cloud, Step Functions). Building it **open and
vendor-neutral** is the strategic white space.

## 2. Why it must ship as framework

- **Universal production concern.** Every agent eventually needs crash-resumable
  runs and human-approval gates for irreversible actions. Neither is
  domain-specific.
- **Load-bearing, hard-to-get-right infra** — checkpoint consistency,
  idempotency / exactly-once side effects, budget-correct resume, suspend/resume
  control flow. Exactly what a framework owns so each agent doesn't reinvent it
  (usually incorrectly).
- **The framework already has the seam.** The feat-017 record/replay system
  already serialises every `Step` to a `Claim` (`__step` category) on a
  `MemoryStore`, and `ReplayLLMClient` already reconstructs a *complete* run from
  those claims. Durable execution is the **promotion of that replay seam into a
  checkpoint-and-resume seam** — a natural extension, not a bolt-on (see §5.2).

### 2.5 Framework-level vs derived-agent-level

**Framework.** The run lifecycle, the per-step trace, the `BudgetPolicy`, the
`RunContext` identity/idempotency machinery, and the strategy loop are all
framework-owned. A consumer cannot make a run resumable or pausable from agent
code without re-implementing the loop.

- **Derived-agent test:** the workaround (a consumer hand-rolling step
  persistence + a bespoke resume loop + an approval gate around their tools)
  re-implements framework internals and must track them across versions —
  fails the test → framework work.
- **How it helps derived agents:** a consumer turns it on with config —
  `execution.durable: true` + `human_in_the_loop.approve_before: [tool:…]` —
  and the framework's loop checkpoints each step and suspends at the gate. No
  agent code. Every org agent benefits identically.

## 3. How derived agents benefit — config, not code

```yaml
# agentforge.yaml
execution:
  durable: true
  store: { driver: sqlite, config: { path: .agentforge/checkpoints.db } }
  checkpoint: per-step        # per-step | per-iteration

human_in_the_loop:
  approve_before: [tool:apply_patch, tool:deploy]
  on_timeout: suspend          # suspend (default) | deny | allow
```

- A long run survives a restart and resumes where it stopped.
- An agent that proposes code changes **pauses for human approval before
  applying a patch** and resumes on approve.
- Composes with the governance spine: HITL approval/denial and each
  resume are **audit events** with stable run identity in the registry.

## 4. Design

### 4.1 The checkpoint model

A **checkpoint** is the minimal serialisable cut needed to resume a run at an
arbitrary step boundary. It is a superset of what recording already writes:

| Field | Source | Already captured by recording? |
|---|---|---|
| `run_id`, `idempotency_seed` | `RunContext` | run_id yes; **seed no** |
| `task`, run `metadata` | `AgentState` | partially |
| `steps` (the trace) | `AgentState.steps` | **yes** (`__step` claims) |
| strategy-local `messages` | `ReActLoop.messages` | no (reconstructable, not persisted) |
| `iteration` cursor | strategy loop | derivable from `step.iteration` |
| **`BudgetPolicy` snapshot** (`spent_usd`, `consumed_tokens`, `iteration`, `error_streak`) | live budget | **no** — the correctness gap (§4.5) |
| `status` (`running` / `suspended` / `awaiting_approval`) + pending tool call | new | no |

`BudgetPolicy` is a plain Pydantic model whose accumulators are all fields, so
the snapshot is a `model_dump`. The trace reuses the exact `_step_payload`
shape recording already produces.

### 4.2 Reusing the recording seam (the promotion thesis)

Recording and resume share a **data model** but not a **delivery mechanism**:

- **Reuse:** the `__step` payload shape, the `Claim` / `MemoryStore` substrate,
  and the category convention. A checkpoint is a `Claim` under a new reserved
  category `__checkpoint`, keyed on `run_id`. `MemoryStore.supersede` gives
  "latest checkpoint per run" for free; `query(category="__checkpoint",
  run_id=…)` retrieves it. No new storage engine.
- **Do NOT reuse:** recording's delivery is the Agent's *post-hoc, batched,
  failure-isolated* `on_step` hooks (they fire after the strategy returns, and
  are swallowed so observability "never breaks the run"). Durable resume needs
  writes **during** the loop, and **strict** failure semantics — a checkpoint
  that silently fails to persist must fail the run, not be ignored.

### 4.3 The checkpoint write point

The write point is **inside the strategy loop**, not the Agent's batch hook.
Every strategy funnels step emission through `StrategyBase._record_step` /
`_call_llm`; the conformance suite already AST-checks that strategies route
through those chokepoints, so a checkpoint callback added there gets uniform
coverage. After each committed step (and budget mutation), the strategy writes
the current checkpoint via the configured store, synchronously, before
proceeding. `checkpoint: per-iteration` batches the write to the top of each
loop iteration (cheaper; coarser resume granularity).

### 4.4 The resume path

`Agent.resume(run_id, *, store)` (or `agentforge run --resume <run_id>`):

1. Load the latest `__checkpoint` claim for `run_id`.
2. Rehydrate `RunContext` via a **new `RunContext.resumed(run_id=,
   idempotency_seed=)`** path that restores the original id + seed instead of
   minting fresh — so idempotency keys for already-executed side-effecting
   tools still match and the tool is not re-run (§4.5).
3. Rehydrate the `BudgetPolicy` from the snapshot (not from pristine config).
4. Rebuild the **live, non-serialisable `RuntimeContext`** (LLM client, tool
   instances) fresh from config — the same split `Agent.run` already does;
   the checkpoint never serialises live objects.
5. Restore strategy-local state (`messages`, `iteration`, `steps`) and re-enter
   the loop at the boundary after the last checkpointed step.

### 4.5 Correctness: no double-spend, no double-fire

The two invariants a naive resume violates:

- **Budget.** `Agent.run` builds a *fresh* `BudgetPolicy` at `spent_usd=0`.
  Resume MUST rehydrate the snapshot, or the cap is silently doubled.
- **Side effects.** A side-effecting tool that ran pre-suspend must not re-run
  post-resume. The framework's `idempotency_key_for` already derives a stable
  key from `idempotency_seed + parts`; resume preserves the seed (§4.4 step 2),
  so a tool guarded by its idempotency key is a no-op on replay. (Tools without
  idempotency keys are the consumer's responsibility — documented; the approval
  gate, §4.6, is the stronger guarantee for genuinely irreversible actions.)

### 4.6 HITL — suspend signal + approval gate

- **Approval gate.** When a strategy is about to dispatch a tool whose name
  matches `human_in_the_loop.approve_before`, it instead: records an
  `awaiting_approval` checkpoint capturing the pending tool call, and raises a
  **suspend control-flow signal** (a new `RunSuspended(AgentForgeError)` subclass
  carrying `run_id`). `Agent.run` catches it and returns a `RunResult` with
  `finish_reason = "suspended"` and the pending approval in `metadata` — the run
  is durably parked, not failed.
- **Approve / deny / resume.** An out-of-band actor calls `Agent.resume(run_id,
  approval=Approve())` / `Deny(reason=…)`. Approve resumes and dispatches the
  pending tool; Deny resumes with the tool result replaced by a denial
  observation so the model can replan. The transport for *delivering* the
  approval (webhook, queue, CLI, chat) is out of scope — the framework exposes
  the suspend state + the resume entrypoint; an adapter delivers it (mirrors how
  A2A/MCP transports sit on the contracts).

### 4.7 New contracts (additive)

- **`CheckpointStore` — reuse vs new ABC.** v1 **reuses `MemoryStore`** + the
  `__checkpoint` category (lowest friction, consistent with recording). A thin
  `CheckpointStore` ABC is introduced **only if/when** leasing (a suspended run
  "owned" by one waiting approver, preventing concurrent resume) or
  cross-store-atomic resume is required. The `"transactions"` capability already
  in the `MemoryStore` vocabulary is the advisory hook for atomic writes. The
  checkpoint store is configured as a `ModuleEntry` (`{driver, config}`)
  resolving via a new `agentforge.checkpoint_stores` entry-point category (or
  reusing `agentforge.memory`).
- **`RunSuspended(AgentForgeError)`** — the suspend control-flow signal.
- **`RunContext.resumed(...)`** — the identity-restoring constructor.
- **`FinishReason`** gains `"suspended"`. (The enum is closed — minor bump per
  ADR-0007. Note `"cancelled"` exists already with zero producers; `"suspended"`
  is semantically distinct — a suspended run is resumable, a cancelled one is
  terminal.)
- **`Approve` / `Deny` / `Edit`** approval value types.

### 4.8 Config surface + Agent wiring

- `execution:` is a top-level nested block (modelled on `retrieval:`): `durable`,
  `store: ModuleEntry`, `checkpoint` cadence, `resume` policy. `human_in_the_loop:`
  is a sibling block: `approve_before`, `on_timeout`, optional escalation hooks.
- `build_execution_from_config` / `build_hitl_from_config` in
  `cli/_build.py` follow the `build_retriever_from_config` template; module-side
  schema validation registers in `validate_module_configs`.
- `Agent.__init__` gains additive kwargs `checkpoint_store=None`,
  `hitl_policy=None` (safe defaults — the locked-surface-additive pattern that
  `record_runs` / `pipeline` / `protocol_bridges` already used; minor bump).

## 5. Public API sketch

```python
# new contracts (agentforge_core)
class RunSuspended(AgentForgeError):
    run_id: str
    pending: PendingApproval | None

@dataclass(frozen=True)
class Approve: ...
@dataclass(frozen=True)
class Deny:  reason: str
@dataclass(frozen=True)
class Edit:  arguments: dict[str, Any]   # approve with modified tool args

# agent surface (additive)
class Agent:
    def __init__(self, *, checkpoint_store: MemoryStore | None = None,
                 hitl_policy: HitlPolicy | None = None, ...): ...

    async def resume(self, run_id: str, *,
                     approval: Approve | Deny | Edit | None = None) -> RunResult: ...
```

```yaml
execution:
  durable: true
  store: { driver: sqlite, config: { path: .agentforge/checkpoints.db } }
  checkpoint: per-step
human_in_the_loop:
  approve_before: [tool:apply_patch]
  on_timeout: suspend
```

## 6. Backward compatibility

Fully additive and **off by default**.

- No `execution:` block → no checkpoints, identical behaviour to today.
- New `Agent` kwargs default to `None`.
- `FinishReason` gains a value (existing consumers that exhaustively match gain
  one arm; everyone else is unaffected).
- The checkpoint store reuses the `MemoryStore` substrate — no new engine.

## 7. Test strategy

- **Offline crash-resume:** run an agent with `FakeLLMClient` + a sqlite
  checkpoint store; kill the loop after step *k* (inject an exception);
  `Agent.resume(run_id)` completes the run; assert the final `RunResult` equals
  the uninterrupted run, the budget is **not** double-counted, and no
  idempotency-keyed tool fired twice.
- **HITL:** configure `approve_before: [tool:x]`; assert the first `run` returns
  `finish_reason="suspended"` with the pending tool call and writes no tool
  side effect; `resume(approval=Approve())` dispatches it; `Deny` replans.
- **Budget durability:** snapshot/rehydrate round-trips `spent_usd` /
  `consumed_tokens` / `iteration`; a resumed run still trips the cap at the
  right point.
- **Idempotency:** the resumed `RunContext` reproduces identical
  `idempotency_key_for(...)` values.
- All offline — no provider, no server (rides the framework's replay ethos).

## 8. Risks & open questions

| Risk / question | Note |
|---|---|
| Tools with un-keyed side effects re-fire on resume | idempotency key is the framework guard; the approval gate is the strong guarantee for irreversible actions; documented. Per-tool "side-effecting" flag a possible follow-up. |
| Checkpoint write latency per step | `checkpoint: per-iteration` (coarser) as the cheaper mode; sqlite local write is sub-ms. Open: async/batched write vs strict-synchronous. |
| Non-serialisable strategy state | only ReAct fully specced here; Plan-Execute/ToT/MultiAgent carry richer loop state — each needs its checkpoint shape (phased; ReAct first). |
| Approval transport | deliberately out of scope — framework exposes suspend state + resume entrypoint; adapters (webhook/queue/CLI/chat) deliver. Open: a reference adapter. |
| `CheckpointStore` ABC vs `MemoryStore` reuse | reuse for v1; promote to a dedicated ABC only when leasing / cross-store atomicity is needed (§4.7). |
| Concurrent resume of one suspended run | needs a lease/claim; deferred with the `CheckpointStore` ABC decision. |
| `"suspended"` vs reusing `"cancelled"` | lean `"suspended"` (resumable ≠ terminal); confirm at ADR time. |

## 9. Out of scope

- Distributed/multi-host orchestration and cross-run workflow durability (a run
  is the unit; pipeline-level durability beyond a single run is separate).
- A specific approval UI / transport (adapters, not core).
- Plan-Execute / ToT / MultiAgent checkpoint shapes (phased follow-ups; ReAct
  is the v1 reference).
- TypeScript port.

## 10. Implementation status (Python)
**Status: proposed.** Needs an ADR (new control-flow + checkpoint contract +
the additive `Agent` kwargs / `FinishReason` change touch locked surfaces).
Suggested chunking when built:
1. Spec + catalogue row + ADR (checkpoint model, suspend signal, identity-restore).
2. `__checkpoint` claim shape + write inside `StrategyBase` (ReAct) + budget
   snapshot; `Agent.resume` crash-resume path; offline crash-resume test.
3. HITL: `approve_before` gate + `RunSuspended` + `finish_reason="suspended"` +
   `Approve`/`Deny`/`Edit` + resume-with-approval; offline HITL test.
4. Config blocks (`execution:` / `human_in_the_loop:`) + `build_*_from_config`
   + module-schema validation + `agentforge run --resume` CLI.
5. Other strategies' checkpoint shapes (phased); reference approval adapter.
6. Status flip + catalogue + roadmap + CHANGELOG.

## 11. References
- feat-017 (recording/replay — the seam this promotes), feat-007
  (`BudgetPolicy` / `RunContext` / idempotency), feat-005 (`MemoryStore`
  substrate), feat-002 (strategies), feat-012/026 (config).
- Prior art for the additive-kwarg-on-locked-`Agent` pattern: `record_runs`,
  `pipeline`, `protocol_bridges`.
- The governance spine (separate epic) consumes HITL approvals as audit events.
