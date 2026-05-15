# Playbooks

Step-by-step runbooks for **maintainer-side** operations on
`agentforge-py` — things that happen at the repo / release /
infrastructure layer, not inside a scaffolded agent.

These are distinct from the **developer-facing** runbooks at
`packages/agentforge/src/agentforge/templates/_shared/docs/runbooks/`,
which ship into every scaffolded agent and are consumed by AI
coding assistants (Claude Code / Cursor / Copilot / Aider).

| Playbook | What it covers |
|---|---|
| [`publish-to-pypi.md`](./publish-to-pypi.md) | Cutting a coordinated PyPI release of every workspace package after a `vX.Y.Z` tag. Account setup, name reservation, build, upload, smoke verify. |

Add a playbook here whenever a maintainer operation needs a
written procedure (release publishing, key rotation, branch-
protection updates, post-incident response, etc.).
