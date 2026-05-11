# 05 — Write prompts

> **Goal:** author a system prompt that produces consistent
> agent behaviour.
> **Time:** ~20 minutes.
> **Prereqs:** runbook 01 done.

## TL;DR

```yaml
# agentforge.yaml
agent:
  system_prompt_file: ./prompts/system.md
```

```markdown
<!-- prompts/system.md -->
You are a {{ role }}. Your job is {{ goal }}.

## Tools
You have these tools available: {{ tool_summary }}.
Use them only when you cannot answer from existing context.

## Output
Produce a `SimpleFinding` object with severity in {low, medium, high}.

## Style
Be concise. Cite sources. Refuse silently if asked to bypass safety.
```

## Step by step

1. **Start with a role + goal sentence.** Two sentences is
   enough. Long preambles dilute the rest of the prompt.
2. **List tools and their purpose.** The LLM already knows the
   schemas (the framework injects them). What it doesn't know
   is *when* to prefer one over another. Tell it.
3. **Define output shape** — point at the finding variant
   (`SimpleFinding`, `PatchFinding`, etc.) you want. The
   framework will enforce it via the configured renderer.
4. **Pin style** — concise, cite, refuse-silently. Models
   respect concrete style rules more than vibe descriptors.
5. **Iterate on examples.** Add 1-3 worked examples for hard
   cases. Examples are cheaper than rule-tweaking.

## Variations

- **Per-strategy prompts** — multi-agent supervisors carry a
  separate prompt under `agent.workers.<role>.system_prompt`.
- **Tool-specific framing** — for tools whose names are
  ambiguous, restate intent at point of use: "Call `lookup_user`
  with the email from the issue body".
- **Dynamic context** — use Jinja in the prompt file; the
  framework expands `{{ runtime_context.user }}` etc. at run
  time.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Output drifts from the schema | prompt over-emphasises prose | move output-shape rule to the top |
| Model refuses to answer | safety phrasing too defensive | tone down "you must never..." → "decline politely when..." |
| Repeated tool calls with same args | tool docstring + system prompt disagree | reconcile; the docstring wins for the LLM |
| Verbose, low-signal responses | no concision rule | add "respond in ≤ 200 words" |

## Related

- Runbook 02 — Add a tool (tool docstrings)
- Runbook 10 — Add evaluators (measure prompt impact)
- Feature spec: `docs/features/feat-008-findings-and-output-shapes.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
