# {{ project_name }}

{{ description }}

## Getting started

```bash
uv sync
cp .env.example .env
# Fill in credentials in .env, then:
python -m {{ project_slug | replace('-', '_') }} "your task here"
```

## Configuration

`agentforge.yaml` is the agent's wiring — model, budget, modules.
See `agentforge config show` for the resolved config and
`agentforge config validate` to check it.

## Upgrades

```bash
agentforge upgrade
```

Pulls in framework updates while preserving your customisations.
See `agentforge status` for what's managed-by-the-framework vs
forked-by-you.
