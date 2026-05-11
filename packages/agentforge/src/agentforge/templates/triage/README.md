# {{ project_name }}

{{ description }} Classifies incoming items by severity + category.
Uses Haiku-tier models — triage is high-volume; the smaller model
keeps cost bounded.

```bash
uv sync
cp .env.example .env
python -m {{ project_slug | replace('-', '_') }} "triage this issue text..."
```

Add a `Coverage` evaluator with a known-issue reference set to
score how completely the agent classifies a batch.
