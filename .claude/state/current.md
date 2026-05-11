---
feature: none
state: idle
branch: main
started_at: null
last_milestone_at: 2026-05-12T03:00
last_shipped: feat-018 shipped via PR #22 (awaiting merge)
blocker: null
flags_for_user: []
---

## Active feature

*None — awaiting next pick.*

## Last shipped

[`feat-018 — Safety guardrails`](../../docs/features/feat-018-safety-and-security-guardrails.md)
shipped in PR #22 with full Python scope:

- ABCs (`InputValidator` / `OutputValidator` / `ToolCallGate`) +
  `ValidationResult` value + `GuardrailPolicy` schema model +
  `GuardrailsConfig` + `GuardrailEntry`.
- Built-in basics: `prompt_injection_basic`, `pii_redact_basic`,
  `capability_check`, `allowlist`. Auto-registered with the
  Resolver under `guardrails.{input,output,tool_gates}`.
- `GuardrailEngine` wrapping LLM + tools transparently; audit
  channel emits one log record per decision plus
  `RunResult.guardrail_events`.
- Conformance harnesses for all three ABCs.
- Four sister packages: `agentforge-guard-llmguard`,
  `agentforge-guard-presidio`, `agentforge-guard-nemo`,
  `agentforge-guard-llamaguard`. Each wraps the upstream SDK
  behind a `Runner` protocol so tests don't need the SDK.

Deviations recorded in the spec §10:

- `GuardrailPolicy` lives in `config.schema` (not `values/`) to
  avoid an import cycle through `values.state`.
- String-form `GuardrailEntry` normalisation deferred (loader
  expects dicts today).
- `modules.guardrails.defaults: true` auto-install of built-ins
  deferred to a follow-up tied to `build_agent_from_config`.
- Latency benchmarking deferred (waits on `eval --bench`).
- TS port deferred.
- Audit sampling / dedicated stream split deferred (events go to
  stdlib `agentforge.audit` logger).

## Next pick candidates (canonical numbering)

- **feat-019** — Developer experience (16 runbooks + AGENTS.md /
  CLAUDE.md / .cursorrules shipped with every scaffold).
  Depends on feat-011 (✓) + feat-017 (✓).
- **feat-013** — MCP integration (consume MCP tool servers +
  expose agent tools as MCP).
- **feat-015** — Pipelines & deterministic tasks.
- **feat-014** / **feat-020** — see specs.
- Vendor observability sub-feats (langfuse/phoenix/evidently/statsd).

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
