# 16 — Configuration reference

> **Goal:** find the canonical shape of every `agentforge.yaml`
> field without re-reading source.
> **Time:** ~5 minutes (lookup).
> **Prereqs:** none.

## TL;DR

```bash
agentforge config schema | less     # print the full JSON schema
agentforge config show --resolved   # see what your YAML actually parsed to
agentforge config validate          # fast-fail on bad keys
```

## Step by step

1. **Schema is the truth.** `agentforge config schema` prints
   the Pydantic-derived JSON schema for `AgentForgeConfig`. No
   guessing.
2. **Resolved view.** `agentforge config show --resolved` prints
   the parsed config with `${ENV_VAR}` interpolation expanded,
   env overlay merged, and CLI overrides applied. Source-of-
   truth for "what will the agent actually run with?"
3. **Validate** before commit. `agentforge config validate` is
   the same parse the runtime does; exit code 2 means the YAML
   has unknown keys, bad types, or invalid env references.

## Top-level sections

| Section | Purpose |
|---|---|
| `agent` | name, model, strategy, system prompt, tools, budget, max_iterations, llm_options |
| `modules` | memory / graph / retriever / evaluators / observability / tools / protocols / guardrails |
| `providers` | named LLM clients (default + judge + embed + custom) |
| `logging` | level, run_id_filter, format (text\|json) |
| `output` | finding variant defaults, renderer choice, thresholds |
| `guardrail_policy` | on_input / on_output / on_tool violation actions, audit_channel, fail_open |

## Environment + override order

CLI flags > `--override` flags > `agentforge.<env>.yaml` overlay >
`agentforge.yaml` > defaults.

```bash
agentforge run \
  --env prod \
  --override agent.budget.usd=20 \
  --override providers.default.model=claude-haiku-4-5 \
  "your task"
```

## Variations

- **Schema export** — `agentforge config schema > schema.json`
  feeds IDE YAML LSPs (vs-code-yaml etc.) for autocomplete.
- **Per-module schemas** — installed modules contribute schemas
  to `modules.<section>.config`. `agentforge config validate
  --strict` enforces.
- **`AGENTFORGE_CONFIG`** + `AGENTFORGE_ENV` + `AGENTFORGE_LOG_
  LEVEL` env vars are the three shortcuts that don't require
  flags.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `unknown field` on a key you expected to be valid | typo or post-major rename | check the schema; spec changes are listed in CHANGELOG |
| `${VAR}` not resolving | env var unset | `agentforge config show --resolved` reports the missing one |
| Override not taking effect | wrong dotted path | overrides are dotted: `agent.budget.usd=10`, not `budget.usd` |
| `fail_open: true` slipped into prod | dev overlay leaked | rotate env-overlay names; only prod overlay shipped to prod |

## Related

- Every other runbook (they all link back here)
- Feature spec: `docs/features/feat-012-configuration-system.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
