# {{ project_name }}

{{ description }} Emits `PatchFinding`s — structured unified diffs
with rationale + confidence — for downstream consumers to apply.

```bash
uv sync
cp .env.example .env
python -m {{ project_slug | replace('-', '_') }} "replace deprecated time.clock() in src/"
```

The agent does NOT apply the patches itself — the consumer (CI
bot, codemod script, etc.) reads `result.findings` and decides.
