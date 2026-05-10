# ADR-0016: Apache 2.0 license

## Metadata

| Field | Value |
|---|---|
| **Number** | 0016 |
| **Title** | Apache 2.0 license |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | licensing, governance |

---

## 1. Context and problem statement

An open-source release requires a license. The choice affects who can
use the framework, how they can contribute, and how comfortable
enterprise legal teams are with adoption.

What license should AgentForge be released under?

## 2. Decision drivers

- Permissive license preferred — maximises adoption (commercial,
  enterprise, internal-tooling)
- Patent grant matters for enterprise-grade adoption
- License must be compatible with the dependencies we expect to ship
  with (Anthropic SDK, OpenAI SDK, Pydantic, FastAPI, etc.)
- Aligns with AI-framework community norms (LangGraph, Strands, BeeAI,
  Pydantic AI all permissive)

## 3. Considered options

1. **Apache 2.0** — permissive + explicit patent grant; LangGraph,
   Strands, BeeAI, Phidata
2. **MIT** — permissive, simpler; Pydantic AI, smolagents
3. **BSD-3-Clause** — permissive, slightly more attribution
4. **MPL 2.0** — file-level copyleft
5. **AGPL-3.0** — strong network copyleft (would lock out commercial
   adoption)

## 4. Decision outcome

**Chosen: Option 1 — Apache 2.0.**

Apache 2.0 is the de-facto standard for permissive open-source
infrastructure libraries with a meaningful patent dimension. The
explicit patent grant matters for enterprise legal review:
contributors agree not to assert patents against users of the licensed
work. This is appreciably better for enterprise adoption than MIT,
which is silent on patents. Apache 2.0 is also what the largest
peer projects (LangGraph, AWS Strands, IBM BeeAI) ship under.

### Positive consequences

- Enterprise legal review is straightforward
- Patent grant reduces patent-troll risk
- Compatible with every dependency we ship
- Familiar to OSS contributors

### Negative consequences (trade-offs)

- Slightly more boilerplate (NOTICE file, license header in source
  files) than MIT
- Apache 2 is incompatible with GPL-2 (cannot be combined with GPL-2
  code) — none of our planned dependencies are GPL-2

## 5. Pros and cons of the options

### Option 1: Apache 2.0 (chosen)

- + Patent grant
- + De-facto standard for AI infrastructure
- − Slightly more file-header overhead than MIT

### Option 2: MIT

- + Smallest license text; familiar
- − No patent grant

### Option 3: BSD-3-Clause

- + Permissive
- − No patent grant; slightly more attribution friction

### Option 4: MPL 2.0

- + File-level copyleft
- − Mixed reception in enterprise contexts; rarer in this ecosystem

### Option 5: AGPL-3.0

- − Network copyleft would lock out most commercial users
- − Would surprise the audience; not aligned with AI-framework norms

## 6. References

- LangGraph (Apache 2.0): https://github.com/langchain-ai/langgraph/blob/main/LICENSE
- Strands Agents (Apache 2.0): https://github.com/strands-agents/sdk-python/blob/main/LICENSE
- BeeAI (Apache 2.0): https://github.com/i-am-bee/beeai-framework/blob/main/LICENSE
- [`docs/design/open-source-framework-plan.md`](../design/open-source-framework-plan.md) §8
