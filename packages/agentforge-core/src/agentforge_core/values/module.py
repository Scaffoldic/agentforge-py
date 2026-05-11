"""`ModuleInfo` — descriptor for a registered module (feat-010).

Returned by `Resolver.list_installed`. Carries enough metadata for
the `agentforge list modules` CLI to render a useful table:
the entry-point category + name, the providing distribution + its
version, and the class object itself (for introspection — e.g.
capabilities, docstring).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModuleInfo(BaseModel):
    """Metadata about one registered module.

    Attributes:
        category: Entry-point group suffix — e.g. `"providers"`,
            `"memory"`, `"tools"`, `"hooks"`, `"renderers"`,
            `"evaluators"`. Matches the second arg to `register`.
        name: Per-category identifier — e.g. `"bedrock"`, `"sqlite"`.
        package: Distribution that provided the class, if known
            (`"agentforge-bedrock"`, `"agentforge"`, etc.). `None`
            for classes registered via `@register` from an unpackaged
            location (typical in tests or single-file agents).
        version: Distribution version (`"0.2.1"`). `None` when
            `package` is `None`.
        cls_qualname: Fully-qualified class name (`"agentforge_bedrock.client.BedrockClient"`)
            — useful for diagnostic output without pulling the class
            object into the renderer.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    category: str = Field(min_length=1)
    name: str = Field(min_length=1)
    package: str | None = None
    version: str | None = None
    cls_qualname: str = Field(min_length=1)
