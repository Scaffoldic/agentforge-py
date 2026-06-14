"""Registered app-config section validation (feat-026 Phase 2).

Phase 1 (enh-002) added the reserved ``app:`` namespace and the
``app_as`` accessor: the framework stored the subtree but validated
nothing inside it — a derived agent owned validation entirely. Phase 2
closes the parity gap with *module* config. A derived agent or plugin
registers a Pydantic schema per ``app.<section>`` through a new
entry-point group, exactly mirroring how modules register their classes
(ADR-0004)::

    [project.entry-points."agentforge.config_sections"]
    graph = "agentforge_graph.config:GraphConfig"

``agentforge config validate`` then validates each registered section
the same way :func:`validate_module_configs` validates ``modules.*``:

- A section present in ``app:`` **and** registered → validated strictly
  against its schema; a typo or bad value fails the command.
- A section present in ``app:`` but **not** registered → left untouched
  (free-form, like an undocumented ``[tool.x]`` in ``pyproject.toml``).
- A registered section **absent** from ``app:`` → nothing to validate.
- A section whose package isn't installed → simply never discovered, so
  validation degrades gracefully with no special-casing (the lenient
  behaviour ``validate_module_configs`` gets from ``strict=False``).

This keeps the single ``app:`` boundary (feat-026 §8): registration maps
names *under* ``app:`` to schemas; it never opens new top-level keys.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from agentforge_core.production.exceptions import ModuleError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from agentforge_core.config.schema import AgentForgeConfig

_log = logging.getLogger("agentforge.config")

#: Entry-point group mapping an ``app.<section>`` name to a Pydantic
#: schema. Parallel to the ``agentforge.<category>`` groups the resolver
#: scans, but consumed here rather than by the runtime resolver (the
#: resolver skips this group — see ``resolver.discover``).
SECTIONS_GROUP = "agentforge.config_sections"


def discover_app_sections() -> dict[str, type[BaseModel]]:
    """Scan the ``agentforge.config_sections`` entry-point group.

    Returns a mapping of section name → Pydantic model class. Entries
    that fail to import, or whose target is not a ``BaseModel`` subclass,
    are skipped with a warning. On a duplicate name across distributions
    the first registration wins (matches the resolver's §8 conflict
    rule).
    """
    sections: dict[str, type[BaseModel]] = {}
    for ep in entry_points(group=SECTIONS_GROUP):
        if ep.name in sections:
            _log.warning(
                "duplicate app-config section %r ignored (first registration wins)",
                ep.name,
            )
            continue
        try:
            model = ep.load()
        except Exception as exc:
            _log.warning(
                "skipping app-config section %r: load failed (%s: %s)",
                ep.name,
                type(exc).__name__,
                exc,
            )
            continue
        if not (isinstance(model, type) and issubclass(model, BaseModel)):
            _log.warning(
                "skipping app-config section %r: %r is not a pydantic BaseModel subclass",
                ep.name,
                model,
            )
            continue
        sections[ep.name] = model
    return sections


def validate_app_config(
    cfg: AgentForgeConfig,
    *,
    sections: Mapping[str, type[BaseModel]] | None = None,
) -> None:
    """Validate each registered ``app.<section>`` against its schema.

    Mirrors :func:`validate_module_configs`. Only sections that are both
    present in ``cfg.app`` and registered via an entry point are checked;
    unregistered sections are left untouched (free-form). A registered
    section that fails its schema always raises :class:`ModuleError` —
    validation failures are fatal, the same as for module config.

    Args:
        cfg: a loaded :class:`AgentForgeConfig` (post-``load_config``).
        sections: pre-discovered section map. Defaults to
            :func:`discover_app_sections`; injectable so tests (and
            future callers with a cached registry) can supply their own.

    Raises:
        ModuleError: a registered ``app.<section>`` subtree fails its
            schema.
    """
    registry = sections if sections is not None else discover_app_sections()
    for name, model in registry.items():
        if name not in cfg.app:
            continue
        try:
            model.model_validate(cfg.app[name])
        except ValidationError as exc:
            raise ModuleError(
                f"app.{name} failed validation: {exc.errors(include_url=False)}"
            ) from exc
