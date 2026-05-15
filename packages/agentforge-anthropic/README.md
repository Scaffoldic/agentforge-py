# agentforge-anthropic

Anthropic native LLM provider for [AgentForge](https://github.com/Scaffoldic/agentforge-py).

Use this package when you want to call Claude directly via
Anthropic's native API rather than through AWS Bedrock. Native
access ships latest-model support, prompt caching, extended
thinking, and per-token streaming the day Anthropic releases them.

## Install

```bash
pip install "agentforge-anthropic[anthropic]"
```

The bare `pip install agentforge-anthropic` install keeps the
package importable for tests; the production runner needs the
`anthropic` SDK, which the `[anthropic]` extra pulls in.

## Use

```python
from agentforge import Agent
from agentforge_anthropic import AnthropicClient

# Direct instantiation
client = AnthropicClient.from_config(
    model="claude-sonnet-4-7",
    api_key="sk-ant-...",  # or omit and use ANTHROPIC_API_KEY
)

# Or via Agent's resolver (recommended)
agent = Agent(model="anthropic:claude-sonnet-4-7")
```

## Capabilities

`AnthropicClient.capabilities()` declares the closed-vocabulary set:

- `tools` — Claude's tool-use API
- `json_mode` — JSON response format via system-prompt addendum
- `caching` — prompt caching with `cache_control: ephemeral` blocks
- `thinking` — extended thinking via `thinking={"type": "enabled", "budget_tokens": ...}`
- `streaming` — per-token streaming via `messages.stream()`

Callers gate optional methods on `client.supports("capability")`
before invoking — the additive contract in
[ADR-0009](https://github.com/Scaffoldic/agentforge-py/blob/main/docs/adr/0009-llm-contract.md).

## Why a separate sister package from `agentforge-bedrock`?

Both implement the same `LLMClient` contract but talk to
different endpoints:

- `agentforge-bedrock` — Bedrock Converse API; Anthropic
  models routed via AWS; cross-region inference profiles;
  AWS IAM auth.
- `agentforge-anthropic` — Anthropic native API; direct;
  bearer-token auth; faster access to new model releases.

A string-id swap (`"bedrock:..."` → `"anthropic:..."`) is the
only change in caller code.

## Testing

Production runner under `# pragma: no cover` wraps the
`anthropic` SDK. Unit tests inject a `FakeAnthropicRunner` (in
`agentforge_anthropic._inmem_runner`) that records every
`messages_create` call. Live integration tests are gated behind
`pytest -m live` and need a real `ANTHROPIC_API_KEY`.

## License

Apache-2.0. See [LICENSE](./LICENSE).
