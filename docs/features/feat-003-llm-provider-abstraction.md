# feat-003: LLM provider abstraction with capability negotiation

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-003 |
| **Title** | LLM & embedding providers — `LLMClient` + `EmbeddingClient` ABCs, named-provider registry, capability negotiation |
| **Status** | shipped (Python — `LLMClient` + `EmbeddingClient` ABCs + named-provider registry; `agentforge-bedrock`) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 |
| **Languages** | both |
| **Module package(s)** | `agentforge-core` (ABC), `agentforge-anthropic`, `agentforge-bedrock`, `agentforge-openai`, `agentforge-litellm`, `agentforge-ollama` |
| **Depends on** | feat-001 |
| **Blocks** | feat-007 (fallback chain) |

---

## 1. Why this feature

Provider lock-in is the silent killer of agent codebases. A team writes against
the Anthropic SDK directly, six months later wants to A/B test Bedrock or
fallback to OpenAI when one is rate-limited, and discovers their tool-calling
plumbing, message formatting, error handling, and streaming code is glued to
Anthropic's exact response shape. The choice is rewrite or stay locked in.

The other failure mode: provider features (prompt caching cuts cost 50–90% on
repeated runs; extended thinking improves hard-reasoning quality; streaming
matters for UX) only get used by agents that hardcode a specific provider,
because the framework's abstraction is the lowest common denominator and
features above that don't exist in the surface.

A third failure mode emerges as agents grow: real production agents use
**multiple LLMs at once**. A typical pipeline:

- A frontier model (Sonnet) for the main reasoning loop
- A small/cheap model (Haiku, gpt-4o-mini) as the LLM-judge for evaluation
- An embedding model (Voyage, OpenAI ada) for retrieval
- Optionally a vision model for image inputs, a routing/classifier model
  for cheap path selection, a summarisation model for memory consolidation

Frameworks that only support "the model" force the developer to wire the
secondary models manually, breaking provider portability and capability
negotiation for everything except the primary.

## 2. Why it must ship as framework

- **Provider portability is a contract, not a hope.** If `LLMClient` lives in
  the framework with a stable signature, swapping providers is a config change.
  If it doesn't, every derived agent reinvents the abstraction at slightly
  different fidelity.
- **Capability negotiation must be honest.** The capability flag pattern
  (`llm.supports("caching")`) only works if the framework defines the capability
  vocabulary. If each agent invents its own flag names, no shared tooling can
  reason about cost optimisation across agents.
- **Fallback chain (feat-007) requires a stable abstraction.** A multi-provider
  fallback needs each provider to look the same to the caller. That's only
  possible if the framework owns the contract.
- **Without framework ownership:** message-format normalisation logic gets
  duplicated, cost-tracking becomes provider-specific, and any cross-cutting
  feature (cost cap, run_id, observability) ends up wrapped per-provider in
  every agent.

## 3. How derived agents benefit

- **Day 1 — model selection by string.** `model="anthropic:claude-sonnet-4.7"`
  picks a provider and model; no imports beyond the extra. Compare to the
  several lines of per-provider client boilerplate other frameworks need per agent.
- **Day 30 — provider swap.** `model="bedrock:anthropic.claude-sonnet-4.7"`,
  `pip install agentforge-bedrock`, redeploy. Tools and prompts unchanged.
- **Day 60 — multi-LLM pipeline.** Declare `providers:` once in YAML; reference
  the right LLM by role across reasoning / evaluation / embedding / vision.
  Different models per role; mixed providers across roles; a single budget cap
  that aggregates across all of them.
- **Day 90 — cost optimisation.** Set `llm.use_caching: auto` in config; if the
  active provider supports caching (declared via `capabilities()`), it's used.
  Fallback to non-cached call is automatic. Agent code is unchanged.
- **Day 180 — fallback chain.** When Anthropic rate-limits, fall through to
  Bedrock. When Bedrock errors, fall through to OpenAI. Configured in YAML;
  `RunResult` records which provider actually served the call.
- **Embedding without a separate library.** `agentforge-voyage`,
  `agentforge-openai`, `agentforge-cohere` all expose `EmbeddingClient`;
  retrieval tools and vector-enabled memory drivers consume any of them by
  name.
- **An agent built today** can adopt a future Anthropic feature (e.g. extended
  thinking) by upgrading `agentforge-anthropic`, with no change to the agent's
  own code — the capability surface auto-extends.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import Agent

# Simple — one model, defaults
agent = Agent(model="anthropic:claude-sonnet-4.7")

# With capability hints
agent = Agent(
    model="anthropic:claude-sonnet-4.7",
    llm_options={"use_caching": "auto", "use_thinking": False, "streaming": False},
)

# Typed instance — escape hatch for full provider control
from agentforge_anthropic import AnthropicClient
client = AnthropicClient(model="claude-sonnet-4.7", api_key="...", thinking_budget=8000)
agent = Agent(model=client)

# Fallback chain (full design in feat-007)
from agentforge import FallbackChain
agent = Agent(model=FallbackChain([
    "anthropic:claude-sonnet-4.7",
    "bedrock:anthropic.claude-sonnet-4.7",
    "openai:gpt-4o",
]))
```

**Multi-provider, by role-name (the production pattern):**

```yaml
# agentforge.yaml
providers:
  reasoning:                          # role → provider config
    type: anthropic
    model: "claude-sonnet-4.7"
    api_key: "${ANTHROPIC_API_KEY}"
    options: { use_caching: "auto" }

  fast-judge:
    type: anthropic
    model: "claude-haiku-4-5"
    api_key: "${ANTHROPIC_API_KEY}"

  embeddings:
    type: voyage
    model: "voyage-large-2"
    api_key: "${VOYAGE_API_KEY}"

  vision:
    type: openai
    model: "gpt-4o"
    api_key: "${OPENAI_API_KEY}"

agent:
  model: "reasoning"                  # references a named provider

modules:
  memory:
    driver: postgres
    config:
      dsn: "${POSTGRES_DSN}"
      embedding_provider: "embeddings"   # vector-search-enabled drivers consume this

  evaluators:
    - correctness:
        judge_provider: "fast-judge"
    - hallucination:
        judge_provider: "fast-judge"
```

Resolver rules: a string with `:` is parsed as `<type>:<model_id>` and
auto-creates an inline (unnamed) provider; a string without `:` is looked
up in the `providers:` registry. Both forms coexist.

```python
# Programmatic access to the registry
from agentforge import current_agent

embeddings = current_agent().providers["embeddings"]
vec = await embeddings.embed("hello world")
```

### 4.2 Public API / contract

```python
# agentforge_core/contracts/llm.py — locked
class LLMClient(ABC):
    """Chat-completion provider. Implements the synchronous request/response
    shape and optional capability methods (caching, thinking, streaming)."""
    @abstractmethod
    async def call(
        self, system: str, messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **provider_options: Any,
    ) -> LLMResponse: ...
    @abstractmethod
    async def close(self) -> None: ...

    def capabilities(self) -> set[str]:
        """Subset of: 'caching', 'thinking', 'streaming', 'tools', 'json_mode',
        'vision', 'parallel_tools'."""
        return set()
    def supports(self, capability: str) -> bool:
        return capability in self.capabilities()

    # Optional — default raises NotImplementedError; providers override.
    async def call_with_cache(self, system, messages, cache_breakpoints: list[int],
                              tools=None, **opts) -> LLMResponse: ...
    async def call_with_thinking(self, system, messages, thinking_budget: int,
                                 tools=None, **opts) -> LLMResponse: ...
    async def stream(self, system, messages, tools=None, **opts) -> AsyncIterator[LLMChunk]: ...

class EmbeddingClient(ABC):
    """Embedding provider. Separate ABC because embedding is a different
    operation from chat (no messages, no tools, returns vectors)."""
    @abstractmethod
    async def embed(self, texts: list[str], *, kind: Literal["query", "document"] = "document"
                    ) -> EmbeddingResponse: ...
    @abstractmethod
    async def close(self) -> None: ...

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    def capabilities(self) -> set[str]:
        """Subset of: 'late_chunking', 'matryoshka', 'multi_modal'."""
        return set()

class LLMResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall]
    stop_reason: str         # "end_turn" | "tool_use" | "max_tokens" | "stop_sequence"
    usage: TokenUsage
    cost_usd: float
    model: str
    provider: str

class EmbeddingResponse(BaseModel):
    vectors: list[list[float]]
    model: str
    provider: str
    cost_usd: float
    tokens: int

class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    thinking_tokens: int = 0
```

**Provider registry — accessed via `Agent.providers`:**

```python
class ProviderRegistry:
    """Owned by Agent. Maps role-name → instantiated client (LLM or Embedding)."""
    def get_llm(self, name: str) -> LLMClient: ...
    def get_embedding(self, name: str) -> EmbeddingClient: ...
    def names(self, kind: Literal["llm", "embedding"] | None = None) -> list[str]: ...

# Construction wiring (simplified)
agent = Agent(
    model="reasoning",                    # name from providers:
    providers={                            # explicit override of YAML
        "reasoning": AnthropicClient(...),
        "fast-judge": AnthropicClient(model="claude-haiku-4-5"),
        "embeddings": VoyageEmbeddingClient(model="voyage-large-2"),
    },
)
```

### 4.3 Internal mechanics

When `Agent` resolves `model="anthropic:claude-sonnet-4.7"`:

1. Split on `:` → `(provider="anthropic", model_id="claude-sonnet-4.7")`.
2. Look up entry point `agentforge.providers.anthropic`.
3. Call `AnthropicClient(model_id="claude-sonnet-4.7", **config_from_yaml)`.
4. The strategy calls `await llm.call(system, messages, tools)` and gets a
   normalised `LLMResponse`. Provider-specific format adaptation (Anthropic vs
   OpenAI vs Bedrock message shape) lives inside each provider package.

`use_caching: auto` workflow inside the strategy:

```
if llm.supports("caching") and len(messages_static_prefix) > threshold:
    response = await llm.call_with_cache(system, messages, [0, k])
else:
    response = await llm.call(system, messages)
```

Cost: every provider returns `cost_usd` in `LLMResponse`. Computed using the
provider's published price table (shipped per-provider; auto-updateable via
config or a periodic price-refresh job).

### 4.4 Module packaging

| Package | Type | Provides | Capabilities at v0.1 |
|---|---|---|---|
| `agentforge-anthropic` | LLM | Anthropic chat | call, caching, thinking, streaming, tools, vision |
| `agentforge-bedrock` | LLM | AWS Bedrock chat | call, streaming, tools |
| `agentforge-openai` | LLM + Embedding | OpenAI chat + `text-embedding-3-*` | call, streaming, tools, json_mode, vision, parallel_tools; embed |
| `agentforge-gemini` | LLM | Google Gemini chat | call, streaming, tools, vision |
| `agentforge-litellm` | LLM | LiteLLM aggregator | call, streaming, tools (capability-by-model) |
| `agentforge-ollama` | LLM + Embedding | Local Ollama | call, streaming; embed |
| `agentforge-voyage` | Embedding | Voyage embeddings | embed (late_chunking, matryoshka) |
| `agentforge-cohere` | LLM + Embedding | Cohere chat + embed | call, streaming, tools; embed |

Each registers via entry points: `agentforge.providers.<name>` for LLMs,
`agentforge.embeddings.<name>` for embeddings. A package can register both
(e.g. `agentforge-openai` registers `agentforge.providers.openai` and
`agentforge.embeddings.openai`).

### 4.5 Configuration

**Inline shorthand** — for simple agents using one provider:

```yaml
agent:
  model: "anthropic:claude-sonnet-4.7"
  llm_options:
    use_caching: "auto"
    use_thinking: false
    streaming: false
    max_tokens: 4096
    temperature: 0.7
```

**Named registry** — for multi-provider agents:

```yaml
providers:
  reasoning:
    type: anthropic
    model: "claude-sonnet-4.7"
    api_key: "${ANTHROPIC_API_KEY}"
    options:
      use_caching: "auto"
      max_tokens: 8192
    timeout_s: 60

  fast-judge:
    type: anthropic
    model: "claude-haiku-4-5"
    api_key: "${ANTHROPIC_API_KEY}"

  reasoning-fallback:
    type: bedrock
    model: "anthropic.claude-sonnet-4.7"
    region: "us-east-1"

  embeddings:
    type: voyage
    model: "voyage-large-2"
    api_key: "${VOYAGE_API_KEY}"

agent:
  model:                                # FallbackChain by role-name
    fallback: ["reasoning", "reasoning-fallback"]

modules:
  memory:
    driver: postgres
    config:
      embedding_provider: "embeddings"

  evaluators:
    - correctness:
        judge_provider: "fast-judge"
```

The two forms coexist within the same YAML — inline shorthand for one-off
references, named registry for shared use across roles.

## 5. Plug-and-play & upgrade story

`pip install agentforge-<provider>` is the entire add flow. The provider
auto-registers; the model string `"<provider>:<model_id>"` is now resolvable.

`agentforge swap` for providers: `agentforge swap llm anthropic openai` updates
`agentforge.yaml`'s `model` and `providers` blocks; pip-installs the new
provider; reminds developer to set the new env vars.

Upgrades within a provider are pip version bumps. The capability set may grow
(e.g. caching arrives in `agentforge-bedrock 0.3`); existing code automatically
benefits when `use_caching: auto`.

## 6. Cross-language parity

`LLMClient` interface and `LLMResponse` shape identical in TS. Providers ship
in both languages — Python first for v0.1, TS catches up. Idiomatic differences:
Python uses `AsyncIterator`; TS uses `AsyncIterable`/`ReadableStream`.

## 7. Test strategy

- **Conformance suite:** every LLM provider passes 20+ tests (basic call, with
  tools, error handling, cost computation, message-shape normalisation). Every
  embedding provider passes 8+ tests (single text, batch, dimensions match
  declared, cost honesty).
- **Capability-claim test:** if a provider declares `"caching"`, its
  `call_with_cache` actually executes against the real SDK in nightly
  integration; declared caps are honest.
- **Registry resolution:** named provider lookup, missing-name error,
  duplicate-name error, mixed inline + named in same YAML.
- **Mock provider:** `MockLLMClient` and `MockEmbeddingClient` (feat-016)
  are real ABC implementations with scripted responses; used by every other
  feature's tests.
- **Cost-table accuracy:** snapshot test against the published price table;
  reviewed quarterly.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Provider response format drifts (vendor adds new field) | Each provider package owns adaptation; framework-level shape stays stable; deprecation warning when an unknown field appears |
| `cost_usd` becomes inaccurate as providers change pricing | Price tables shipped per-provider package; updated on minor bumps; alternatively allow override via `providers.<name>.price_overrides` |
| Capability vocabulary grows uncontrollably | Capability strings are a closed enum at the contract level; new caps require feature doc + minor bump |
| LiteLLM as a meta-provider hides errors (a known footgun in frameworks that route everything through it) | We ship `agentforge-litellm` for breadth, but recommend native providers for production; document the trade-off |
| Vision / multi-modal input shape | Out of scope for v0.1; add as a capability `"vision"` with `MessageContent` extension in a follow-up feature |
| Should embeddings be a separate ABC or a `LLMClient` capability? | Separate ABC (`EmbeddingClient`). Embedding has different inputs/outputs, different cost models, often different provider (e.g. Anthropic users use Voyage); coupling them confuses the surface |
| Cost cap across multiple providers (judge + embedding + reasoning) | Single per-run `BudgetPolicy` (feat-007) aggregates spend across every provider used during the run; each provider returns `cost_usd`, the registry sums |
| Provider-name collisions in registry vs entry-point names | Registry names live in the agent's YAML; entry-point names are the *types* (`anthropic`, `voyage`); resolver disambiguates by position (`type:` is the lookup key, the YAML key is the role) |
| Embedding model version drift (re-embedding cost when model upgrades) | Driver records `(provider, model)` tuple in vector metadata; mismatched embeddings flagged by memory driver, not silently used |

## 9. Out of scope

- A unified prompt template engine. We don't normalise across providers'
  system-prompt quirks; that's the developer's job (or a tool's).
- Local-model finetuning. Use Ollama / vLLM through the provider; finetuning
  pipelines are a different product.
- Cost forecasting before a run starts. We bound runs with `BudgetPolicy`
  (feat-007); pre-run forecasting requires per-task cost models that are
  out of scope.

## 10. References

- [`architecture.md`](../design/architecture.md) §4
- [`design-principles.md`](../design/design-principles.md) — P1, P9
- feat-001 (`Agent` resolves the LLM client)
- feat-007 (FallbackChain wraps providers)
- Archived: `docs/archive/cr/CR-005b-coverage-ratchet-and-capability-llm.md`,
  `CR-008-cross-provider-fallback.md`

---

## Implementation status

**Status: partial (Python).** Bedrock driver landed as
[Scaffoldic/agentforge-py PR #4](https://github.com/Scaffoldic/agentforge-py/pull/4)
on `feat/003-bedrock-provider`.

Shipped:

- `LLMClient` ABC + `EmbeddingClient` ABC with capability vocabulary
  (`{"tools", "json_mode", "caching", "thinking", "streaming"}`).
- `agentforge-bedrock` driver — first first-party Tier-3 provider.
  `BedrockClient` over aioboto3, supports prompt caching
  (`cachePoint` blocks), extended thinking
  (`additionalModelRequestFields.thinking`), streaming via
  ConverseStream, plus `BedrockEmbeddingClient` (Titan + Cohere).
  Cross-region inference profiles (`us.…`, `eu.…`, `apac.…`,
  `global.…`) supported transparently.
- Resolver pattern for `Agent(model="bedrock:…")` lookup.
- Pricing entry-point with strip-cross-region-prefix logic.
- **enh-004** — `providers.<name>.config` is passed through to the
  provider constructor (`region` / `aws_profile` / `role_arn` /
  `timeout_seconds` reach the client from YAML; previously dropped —
  a plain `type:model` string carries only the model id, and an
  unknown config key now raises `ModuleError`). The Bedrock chat +
  embedding clients gained `role_arn` (+ `role_session_name`) STS
  assume-role. Runbook 13 documents the AWS Bedrock path
  (inference-profile ids, IAM, assume-role). Closes #92.

Not yet shipped (backlog):

- **First-party Anthropic provider** (separate from Bedrock; same
  `LLMClient` shape).
- **OpenAI / Azure provider.**
- **`FallbackChain`** wrapper that ties multiple providers together —
  the spec describes it as part of feat-007 (Production rails) work.

TypeScript port pending.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented "how do I…" content. This is the canonical
home for the feature's runbook; feat-011 / feat-019 consume these
sections into scaffolded agent projects.

### How do I point an agent at Bedrock?

```python
from agentforge import Agent

agent = Agent(model="bedrock:us.anthropic.claude-sonnet-4-5-20250929")
```

`agentforge-bedrock` registers under the `bedrock:` prefix at
import. AWS credentials follow the standard boto3 chain —
`AWS_PROFILE`, `AWS_REGION`, instance roles, etc. Override
explicitly when needed:

```python
from agentforge_bedrock import BedrockClient

client = BedrockClient(
    model_id="us.anthropic.claude-sonnet-4-5-20250929",
    region="eu-west-1",
    aws_profile="prod",
    max_retries=5,
    timeout_seconds=120.0,
)
agent = Agent(model=client)
```

### How do I use cross-region inference profiles?

Use the geo-prefixed model id — Bedrock routes for you:

| Prefix | Destination |
|---|---|
| `us.anthropic.claude-...` | US regions |
| `eu.anthropic.claude-...` | EU regions |
| `apac.anthropic.claude-...` | APAC regions |
| `global.anthropic.claude-...` | Global pool |

Source region (`region=` or `AWS_REGION`) only controls where the
request enters Bedrock; pricing strips the geo prefix when looking
up the cost table, so a `us.…` profile is priced the same as the
region-pinned variant.

### How do I enable prompt caching?

Caching is opt-in via the `use_caching` option on a per-call basis.
feat-012's config schema now ships `agent.llm_options: dict` for
per-call options; wiring strategies to honour
`llm_options={"use_caching": "auto"}` from config is a small Agent-
level follow-up. Today, instantiate `BedrockClient` directly and
call `call_with_cache(...)` — it emits `cachePoint` blocks at the
system prompt and last tool result. Requires Anthropic models on
Bedrock; `chain.supports("caching")` advertises availability.

### How do I enable extended thinking?

Same shape — call `call_with_thinking(...)` on a `BedrockClient`.
This adds `additionalModelRequestFields.thinking` to the Converse
request. Reasoning tokens count toward `tokens_out` and are
charged at the standard rate.

### How do I use embeddings?

`agentforge-bedrock` ships `BedrockEmbeddingClient` for Titan and
Cohere:

```python
from agentforge_bedrock import BedrockEmbeddingClient

embedder = BedrockEmbeddingClient(model_id="amazon.titan-embed-text-v2:0")
vec = await embedder.embed("a sentence to encode")
print(vec.dimensions, len(vec.embedding))
```

Combine with a `VectorStore` + `Retriever` (feat-005 Runbook) for
RAG.

### How do I read the cost of a call?

`LLMResponse.cost_usd` is computed from the published price table
shipped with each provider package:

```python
result = await agent.run("…")
print(result.cost_usd)  # sum across every LLM call in the run
```

Per-step costs live on each `Step.cost_usd`. Cross-region
inference profiles are priced via the stripped (region-pinned)
model id; if your cost looks off, check that the pricing
entry-point recognises the prefix you're using.

### How do I add a custom provider?

Subclass `LLMClient` and register at import:

```python
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.resolver import register_provider

@register_provider("mycorp")
class MyCorpClient(LLMClient):
    def __init__(self, *, model_id: str) -> None:
        self._model_id = model_id

    async def call(self, system, messages, tools=None): ...
    async def close(self) -> None: ...
    def capabilities(self) -> set[str]:
        return {"tools"}
```

If your provider validates tool names, call
`agentforge_core.contracts.tool.validate_tool_name(t.name)` for each
tool while building the request — it raises `ToolNameInvalidError`
(a `ProviderError`) for any name outside `^[a-zA-Z0-9_-]{1,64}$`, the
charset the built-in providers share. This keeps the vendor-agnostic
promise: a tool that works on one provider works on yours.

Now `Agent(model="mycorp:foo-bar")` resolves to your class. For
distribution, expose the import via a `agentforge.providers.mycorp`
entry-point in `pyproject.toml`; feat-010's resolver auto-loads
every `agentforge.*` entry point on first `Resolver.resolve()` /
`Agent.run()`, so a `pip install` is enough — no explicit import
needed.

### When should I NOT use Bedrock?

- **Streaming-first agents on Anthropic-direct.** If you need the
  absolute lowest streaming latency to Anthropic models, the
  first-party `agentforge-anthropic` provider (backlog) will land
  with native SSE; Bedrock streams through Converse with slightly
  higher overhead.
- **Models not in your region.** Bedrock's model catalogue varies
  by region; use cross-region inference profiles (above) or pick a
  different provider.
- **Local / on-prem models.** Use `agentforge-ollama` or
  `agentforge-vllm` (backlog) — no AWS dependency.
