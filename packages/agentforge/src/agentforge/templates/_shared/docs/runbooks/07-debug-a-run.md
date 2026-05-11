# 07 — Debug a run

> **Goal:** reproduce a failed run locally and step through what
> the agent saw.
> **Time:** ~15 minutes.
> **Prereqs:** runbooks 01 + 06.

## TL;DR

```bash
# In the offending env (or anywhere with a recorded run):
agentforge run --record "the failing task"
# Note the printed run_id, then:
agentforge debug --replay <run_id>
> step
> state
> inspect tool_call.arguments
> quit
```

## Step by step

1. **Reproduce with recording.** `agentforge run --record "..."`
   persists every `Step` to the configured memory store under
   `category="__step"`. Without `--record`, the trace dies with
   the process.
2. **Pick the run_id.** It prints to stdout at run end (also
   present on `RunResult.run_id`).
3. **Open the REPL** with `agentforge debug --replay <run_id>`.
   Reads from memory; no LLM call required.
4. **Step + inspect.** `step` advances; `state` prints the
   current step's payload; `inspect <dotted-path>` drills in
   (`inspect tool_call.arguments`). `back` rewinds; `steps`
   lists the whole trace.
5. **Bisect.** If the failure is in step 17 of 22, `--to-step
   N` on `agentforge run --replay` re-runs the loop up to step
   N with the recorded LLM responses and stops.

## Variations

- **Replay tools** — `replay_tools(memory, run_id, [your_tools])`
  returns wrappers whose `run()` returns the recorded
  observation. Pair with `ReplayLLMClient.from_recording(...)`
  for byte-identical replays.
- **Cassette replay** — `agentforge run --replay <run_id> --to-
  step 5` is the CLI surface around the same primitives.
- **Tracing** — the OTel root span ID is in
  `RunResult.metadata` if observability is enabled (runbook 12);
  cross-reference with your APM dashboard.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No recorded steps for run_id` | run was not recorded | add `--record` next reproduction; configure `modules.memory` |
| Replay diverges from original | tool or LLM args drifted | use `ReplayLLMClient.from_recording` AND `replay_tools` together |
| REPL EOF errors | piped stdin without newline | append `\n` to the scripted input |
| `ReplayExhausted` | trying to replay further than recorded | task changed; re-record with the new task |

## Related

- Runbook 06 — Test your agent
- Runbook 08 — Add memory (recording lives in the memory store)
- Feature spec: `docs/features/feat-017-cli-runtime.md` (debug,
  replay)

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
