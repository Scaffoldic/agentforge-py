# ADR-0001: Framework name — AgentForge

## Metadata

| Field | Value |
|---|---|
| **Number** | 0001 |
| **Title** | Framework name — AgentForge |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | brand, naming |

---

## 1. Context and problem statement

The framework needed a public, brandable name. The internal predecessor
("EVA / `eva-ai-agent-template`") is a private cookiecutter; an open-source
release demands a name that is short, memorable, claimable on PyPI and
GitHub, and resonant with the framework's "compose-from-modules" identity.

How do we name the framework so that the brand reinforces the architecture
and is operationally available across registries?

## 2. Decision drivers

- One or two short syllables, easy to type and say
- Available on PyPI, GitHub org, npm, and a `.dev` or `.io` domain
- Evokes composition / modularity / craft, not just "agents"
- Not colliding with another agent framework's name
- Reads well as a prefix for sub-packages: `<name>-core`, `<name>-anthropic`
- Distinct from internal predecessor (EVA) so the public release is a clean break

## 3. Considered options

1. **Lattice** — grid of swappable cells held by a shared structure
2. **Tessera** — Latin for a single mosaic tile
3. **Forge / AgentForge** — the act of forging composable parts into a working agent
4. **Atrium** — open central space modules plug into
5. **Plinth / Quanta / Pluxe / Klik** — coined / niche options

## 4. Decision outcome

**Chosen: Option 3 — AgentForge.**

The name reads as a verb ("forge an agent") which captures the framework's
behaviour: starting from a small core, you forge an agent by adding modules.
"Forge" connotes craft and assembly — appropriate for a plug-and-play
framework. Compound is one word, no hyphens needed, easy to pronounce in
both English and most non-English languages. Available on PyPI as
`agentforge` and on GitHub. The `forge` morpheme is widely understood
without needing a dictionary.

### Positive consequences

- Clean PyPI / npm naming: `agentforge`, `agentforge-anthropic`, etc.
- Folder/CLI naming follows naturally: `agentforge new`, `agentforge add`
- Imports are pleasant: `from agentforge import Agent`
- TS package can be `agentforge` flat or `@agentforge/core` scoped
- Brand-friendly for a website at `agentforge.dev` (subject to availability)

### Negative consequences (trade-offs)

- "Forge" is in active use across dev tooling generally (Forge templates, etc.) — not in the agent space specifically, but trademark sweeps are required
- Compound name is slightly longer than one-word options (Lattice, Letta)

## 5. Pros and cons of the options

### Option 1: Lattice

- + Strong metaphor (grid of swappable cells)
- + Short, one word
- − Palantir has a "Lattice" defense product
- − PyPI `lattice` taken (small geometry library)

### Option 2: Tessera

- + Distinctive, no agent-framework collision
- + Mosaic metaphor maps directly to plug-and-play
- − Slightly obscure word; harder to spell on first hearing

### Option 3: AgentForge

- + Verb-as-name reinforces the action ("forge an agent")
- + No agent-framework collision
- + Compound parses well in package names
- − Two-syllable compound; longer than one-word options

### Option 4: Atrium

- + Calm, architectural, professional
- − Atrium Health and Atrium UI exist; trademark risk

### Option 5: Coined names

- + Available; distinctive
- − Memorable but feels gimmicky; non-English speakers may struggle

## 6. References

- [`docs/design/open-source-framework-plan.md`](../../docs/archive/...) — earlier naming exploration
- [`docs/README.md`](../README.md) — public framing of the brand
