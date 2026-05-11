# {{ project_name }}

{{ description }} Answers questions from documentation / source.
Outputs `NarrativeFinding`s — markdown prose with citations.

```bash
uv sync
cp .env.example .env
python -m {{ project_slug | replace('-', '_') }} "how does the auth flow work?"
```

For real RAG, install `agentforge-memory-sqlite` (or postgres),
wire `modules.memory.driver` and `modules.retriever` in
`agentforge.yaml`, and index your corpus.
