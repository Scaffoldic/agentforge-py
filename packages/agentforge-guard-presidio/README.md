# agentforge-guard-presidio

[Microsoft Presidio](https://microsoft.github.io/presidio/) PII
detection + anonymisation for AgentForge guardrails (feat-018).

Adds the `presidio` validator to the `agentforge.yaml`
`modules.guardrails.output` section:

```yaml
modules:
  guardrails:
    output:
      - presidio:
          entities: ["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON",
                     "CREDIT_CARD", "US_SSN", "IP_ADDRESS"]
          score_threshold: 0.5
          action: "redact"   # "redact" | "score-only"
```

```bash
agentforge add module guard-presidio
```

The default `score_threshold` of `0.5` is Presidio's recommended
balance between recall and false positives. Set lower for stricter
redaction, higher to reduce noise. `action: "score-only"` reports
the violations without modifying the content.
