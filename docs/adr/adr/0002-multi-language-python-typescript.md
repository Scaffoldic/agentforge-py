# ADR-0002: Multi-language: Python and TypeScript with contract parity

## Metadata

| Field | Value |
|---|---|
| **Number** | 0002 |
| **Title** | Multi-language: Python and TypeScript with contract parity |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, scope |

---

## 1. Context and problem statement

Most agent frameworks ship in one language. LangChain, CrewAI, Pydantic AI,
LlamaIndex are Python-only; Vercel AI SDK and Mastra are TS-only. Real
teams in 2026 are increasingly heterogeneous — backend engineers on Python,
frontend / fullstack on TypeScript, both wanting to build agents.

How do we serve both audiences without doubling our ABCs and risking drift
between the two implementations?

## 2. Decision drivers

- Demand from both ecosystems is real and growing
- Cross-language parity demonstrates architectural rigour (the contract
  is real, not implementation-flavoured)
- A team that ships a chatbot in TS and a code reviewer in Python should
  use the same framework
- Drift between language implementations is a known failure mode (cf.
  AutoGen v0.2 / v0.4 schism, BeeAI's smaller TS surface)
- Maintainer cost doubles — needs to be acknowledged and bounded

## 3. Considered options

1. **Python only** — like LangChain, Pydantic AI; most popular path
2. **TypeScript only** — like Vercel AI SDK, Mastra; smaller community but growing
3. **Python + TypeScript with contract parity** — both languages, identical contracts, idiomatic surfaces
4. **Python primary + TS via WASM bridge** — single source of truth, generated TS bindings

## 4. Decision outcome

**Chosen: Option 3 — Python + TypeScript with contract parity.**

The framework's value proposition (ABCs as the locked contract,
implementations interchangeable) is the same proposition that makes
cross-language parity coherent. We define one contract, write idiomatic
implementations in each language, and verify behavioural equivalence in
shared test fixtures. Python ships first during 0.x; TS catches up to
parity by 0.4. Modules ship in both languages where SDK ecosystems allow;
the contract layer is identical from day 1.

### Positive consequences

- Serves both audiences from one project
- Contract discipline is enforced by the multi-language test fixture
- Cross-language interop (A2A) becomes natural
- Marketing differentiator vs Python-only competitors

### Negative consequences (trade-offs)

- Maintainer time roughly doubles for any contract change
- Some modules (e.g. NeMo Guardrails, LLM Guard) are Python-only upstream;
  TS lags or never catches up
- TS scaffolding gets a native engine port (ADR-0021), not a Copier
  wrapper — additional implementation work but cleaner long-term

### Repo structure (locked 2026-05-09)

- **Two separate language repos**: `agentforge-py` (Python),
  `agentforge-ts` (TypeScript). Each has its own git history, CI,
  releases.
- **Within each language repo**, a workspace tool manages the
  multi-package framework: `uv` workspaces inside `agentforge-py`;
  `pnpm` workspaces inside `agentforge-ts`.
- **npm naming is scoped**: `@agentforge/core`, `@agentforge/anthropic`,
  `@agentforge/memory-postgres`, etc. PyPI stays flat (`agentforge`,
  `agentforge-anthropic`). The asymmetry is normal in 2026.
- **The current `ai-agents/` directory** is the design workspace —
  docs, ADRs, `.claude/` development pipeline, doc templates. The
  language implementations live in their own repos and are pulled in
  here only as references when the user wants both visible together.

## 5. Pros and cons of the options

### Option 1: Python only

- + Lowest maintainer cost
- + Largest agent ecosystem to date
- − Excludes a growing TS audience
- − Misses A2A interop value

### Option 2: TypeScript only

- + Simpler runtime story (no async complexity)
- − Tiny share of agent ecosystem
- − Most LLM SDKs / safety tools / persistence drivers Python-first

### Option 3: Both with parity (chosen)

- + Wide audience reach
- + Architectural credibility (parity proves the contract)
- − Roughly 2× contract surface to maintain
- − Some modules can ship Python-first; TS catches up later

### Option 4: WASM bridge

- + Single source of truth
- + No drift possible
- − User-visible WASM in a TS project is hostile DX
- − Performance and packaging penalties
- − No prior art in this space

## 6. References

- [`docs/design/architecture.md`](../design/architecture.md) §10 — cross-language parity
- ADR-0007 — ABC + Protocol contracts as stable surface
- [`docs/design/design-principles.md`](../design/design-principles.md) — P9 (cross-language parity at contract layer)
