# 11 — Add safety guardrails

> **Goal:** layer input validation, output redaction, and tool-
> call gating onto your agent.
> **Time:** ~15 minutes.
> **Prereqs:** runbook 02.

## TL;DR

```yaml
# agentforge.yaml
modules:
  guardrails:
    defaults: true               # framework basics auto-installed
    input:
      - prompt_injection_basic
    output:
      - pii_redact_basic
    tool_gates:
      - capability_check
      - allowlist:
          allowed: ["web_search", "calculator"]
guardrail_policy:
  on_input_violation: block
  on_output_violation: redact
  on_tool_violation: block
  fail_open: false
```

## Step by step

1. **Start with the basics.** `prompt_injection_basic` +
   `pii_redact_basic` + `capability_check` cover the obvious
   cases out of the box; they ship with the framework.
2. **Add an allowlist** if your tools include anything
   `destructive`. `capability_check` already denies destructive
   tools by default; `allowlist` is a tighter second layer.
3. **Pick a policy.** `block` is the safe default for input and
   tool violations; `redact` for outputs lets the run complete
   with PII stripped. `fail_open: false` (the default) treats
   validator exceptions as failures.
4. **Add vendor modules** when basics aren't enough. `presidio`
   for richer PII, `llmguard` for richer prompt-injection,
   `nemo` for programmable Colang rails, `llamaguard` for the
   Llama Guard 3 classifier. Each is a separate pip install.
5. **Audit decisions.** Every validator call emits an
   `agentforge.audit` log record and appends to
   `RunResult.guardrail_events`. Configure your log pipeline to
   stream the audit logger to a security store.

## Variations

- **Custom validator.** Subclass `InputValidator` /
  `OutputValidator` / `ToolCallGate` from
  `agentforge_core.contracts.guardrails`, register with
  `@register("guardrails.input", "my-name")`.
- **Score-only mode** — Presidio + LLM Guard support a
  `score-only` action that reports without modifying content.
  Useful for triage dashboards.
- **Conformance test custom validators** with
  `run_input_validator_conformance` / `run_output_validator_
  conformance` / `run_tool_gate_conformance` from
  `agentforge.testing`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `GuardrailViolation` at startup | input flagged | inspect `RunResult.guardrail_events`; relax to `warn` if false-positive |
| PII still in output | regex basic doesn't catch your case | install `agentforge-guard-presidio` for richer detection |
| Destructive tool still ran | `capability_check` was disabled in config | re-enable; ensure `Tool.capabilities` includes `"destructive"` |
| Tests fail with `GuardrailViolation` | tests use prompts that look like injection | mock the validator in tests, or rephrase the test prompt |

## Related

- Runbook 12 — Add observability (audit stream)
- Runbook 14 — Deploy your agent (policy hardening)
- Feature spec: `docs/features/feat-018-safety-and-security-guardrails.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
