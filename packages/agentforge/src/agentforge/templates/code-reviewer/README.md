# {{ project_name }}

{{ description }} Reviews a diff and emits structured `SimpleFinding`s.

```bash
uv sync
cp .env.example .env
python -m {{ project_slug | replace('-', '_') }} "review the diff at /path/to.patch"
```

Drop in evaluator graders (faithfulness / correctness) once you
have rubric examples — see the commented stub in `agentforge.yaml`.
