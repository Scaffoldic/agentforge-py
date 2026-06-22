# agentforge-governance

The governance spine for [AgentForge](https://github.com/Scaffoldic/agentforge-py).
The contracts live in `agentforge-core`; this package ships the default,
offline, zero-dependency drivers.

**feat-029 — identity.** `LocalIdentityProvider` issues, resolves, and
verifies `Principal`s in-process with HMAC-signed credentials (no network,
deterministic for tests). Principal ids use the portable URN scheme
`agentforge:agent:<org>/<name>@<version>`.

```python
from agentforge_governance import LocalIdentityProvider

idp = await LocalIdentityProvider.from_config(org="finance")
p = await idp.issue(name="invoice-reconciler", owner="finance-platform")
token = await idp.credential(p)
assert (await idp.verify(token)).id == p.id
```

Via YAML:

```yaml
governance:
  identity:
    provider: local
    name: invoice-reconciler
    owner: finance-platform
    attributes: { env: prod }
```

Registry, policy, and audit drivers land here as their pillars ship.
