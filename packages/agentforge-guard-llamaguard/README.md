# agentforge-guard-llamaguard

Meta [Llama Guard 3](https://huggingface.co/meta-llama/Llama-Guard-3-8B)
classifier for AgentForge guardrails (feat-018).

Adds the `llamaguard` validator to both `input` and `output`
sections of `modules.guardrails`. Unlike the other guard modules,
this one needs an `LLMClient` — Llama Guard runs as a chat model
producing one of `safe` / `unsafe S1..S14` for each turn:

```yaml
modules:
  guardrails:
    input:
      - llamaguard:
          model: "bedrock:meta.llama3-guard-3-8b-instruct-v1:0"
    output:
      - llamaguard:
          model: "bedrock:meta.llama3-guard-3-8b-instruct-v1:0"
```

```bash
agentforge add module guard-llamaguard
```

The validator constructs an `LLMClient` lazily from the model
string via the framework's resolver, so any provider that
implements `LLMClient` (Bedrock, local Ollama via a custom
provider, etc.) can host the guard model.
