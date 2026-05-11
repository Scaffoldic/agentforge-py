"""Entry-point discovery for feat-010.

Scans `importlib.metadata.entry_points()` for groups starting with
`agentforge.` and registers each entry against the global resolver.
A group named `agentforge.<category>` (e.g. `agentforge.providers`,
`agentforge.memory`) maps to the resolver's `<category>` slot.

The scan runs lazily — `Resolver.resolve` calls `ensure_discovered()`
on first use. Tests that want to start with a clean slate can call
`Resolver.global_().clear()` (also resets the discovery cache).

Conflict handling: if two distributions register under the same
`(category, name)` pair, the first one to register wins (entry-point
iteration order is the source). The resolver's own `register`
method raises `ModuleError` when the second registration arrives at
a different class — we catch that, log, and let the first win. This
matches the spec's §8 "Conflict resolution" entry while keeping the
runtime predictable.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.module import ModuleInfo

if TYPE_CHECKING:
    from agentforge_core.resolver.resolve import Resolver

_log = logging.getLogger("agentforge.resolver")

_GROUP_PREFIX = "agentforge."

# Module-level state held on a mutable list to avoid `global` (PLW0603).
_discovered: list[bool] = [False]
# Cache of resolved ModuleInfo per registered entry — keyed by
# `(category, name)`. Populated alongside the registry by
# `discover_entry_points`.
_module_info_cache: dict[tuple[str, str], ModuleInfo] = {}


def ensure_discovered(resolver: Resolver) -> None:
    """Lazy hook — runs `discover_entry_points` once per resolver lifetime.

    Resolver methods that need entry-point-registered modules call
    this on entry. Safe to call repeatedly; only the first call does
    work.
    """
    if _discovered[0]:
        return
    discover_entry_points(resolver)


def discover_entry_points(resolver: Resolver, *, force: bool = False) -> int:
    """Scan `agentforge.*` entry points and register them on `resolver`.

    Args:
        resolver: Target resolver — typically `Resolver.global_()`.
        force: When `True`, re-scan even if discovery has already run
            (used by tests and by `Resolver.clear()`).

    Returns:
        Number of entries registered (excluding conflicts skipped).
    """
    if _discovered[0] and not force:
        return 0
    registered = 0
    eps = entry_points()
    # `entry_points()` returns an `EntryPoints` selectable view on
    # 3.10+; iterate by group prefix.
    for ep in eps:
        if not ep.group.startswith(_GROUP_PREFIX):
            continue
        category = ep.group[len(_GROUP_PREFIX) :]
        try:
            cls = ep.load()
        except Exception as exc:
            _log.warning(
                "skipping entry point %s.%s: load failed (%s: %s)",
                ep.group,
                ep.name,
                type(exc).__name__,
                exc,
            )
            continue
        if not isinstance(cls, type):
            _log.warning(
                "skipping entry point %s.%s: target %r is not a class",
                ep.group,
                ep.name,
                cls,
            )
            continue
        try:
            resolver.register(category, ep.name, cls)
        except ModuleError as exc:
            # Another distribution already registered the same key —
            # first wins per spec §8. Log and move on.
            _log.warning(
                "entry-point conflict %s.%s ignored: %s",
                ep.group,
                ep.name,
                exc,
            )
            continue
        # Carry the source distribution metadata for `list_installed`.
        dist = ep.dist
        info = ModuleInfo(
            category=category,
            name=ep.name,
            package=dist.name if dist is not None else None,
            version=dist.version if dist is not None else None,
            cls_qualname=f"{cls.__module__}.{cls.__qualname__}",
        )
        _module_info_cache[(category, ep.name)] = info
        registered += 1
    _discovered[0] = True
    return registered


def reset_discovery() -> None:
    """Clear the discovery cache. Called from `Resolver.clear()` and
    by tests that want a clean slate."""
    _discovered[0] = False
    _module_info_cache.clear()


def module_info_for(category: str, name: str, cls: type) -> ModuleInfo:
    """Return cached `ModuleInfo` if the entry was discovered via
    entry points; otherwise synthesise one from `cls.__module__` /
    `__qualname__` (for `@register`-registered classes).
    """
    cached = _module_info_cache.get((category, name))
    if cached is not None:
        return cached
    return ModuleInfo(
        category=category,
        name=name,
        package=None,
        version=None,
        cls_qualname=f"{cls.__module__}.{cls.__qualname__}",
    )
