# agentforge-core

The stable contract layer for AgentForge. ABCs, Protocols, and value
types that every module implements.

## What's in here

(Once feat-001 lands.)

- `LLMClient`, `EmbeddingClient` — provider abstractions
- `ReasoningStrategy` — agent loop shape
- `Tool` — pluggable capabilities
- `MemoryStore`, `GraphStore` — persistence
- `Evaluator` — post-run scoring
- `InputValidator`, `OutputValidator`, `ToolCallGate` — real-time safety
- `Finding` — output Protocol with shipped variants
- `BudgetPolicy`, `RunContext`, `RunIdFilter` — production rails
- Value types: `Claim`, `Step`, `RunResult`, etc.

This package is a **locked contract** — adding a method to an ABC is a
major version bump. See ADR-0007.

## What's NOT in here

- Reference implementations (`ReActLoop`, `InMemoryStore`, etc.) — those
  live in `agentforge`
- Provider clients — those live in `agentforge-anthropic`, etc.
- Anything that does I/O

## Install

```bash
pip install agentforge-core
```

Most users install `agentforge` directly, which depends on this package.

## License

Apache 2.0.
