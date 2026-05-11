# agentforge-guard-llmguard

LLM Guard scanners for AgentForge guardrails (feat-018).

Wraps the [`llm-guard`](https://llm-guard.com) library. Adds the
`llmguard` validator to the `agentforge.yaml`
`modules.guardrails.input` section:

```yaml
modules:
  guardrails:
    input:
      - llmguard:
          scanners: ["prompt_injection", "ban_substrings", "secrets"]
          ban_substrings: ["password", "api_key"]
```

```bash
agentforge add module guard-llmguard
```

The shipped scanner subset covers `prompt_injection`, `jailbreak`,
`ban_substrings`, and `secrets`. The full upstream scanner catalogue
remains accessible by passing additional names through the
`scanners` list — LLM Guard resolves them server-side.
