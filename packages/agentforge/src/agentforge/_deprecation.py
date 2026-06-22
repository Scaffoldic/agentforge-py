"""Deprecation registry (enh-006 part 3).

`@deprecated` marks a superseded framework seam: it emits a
`DeprecationWarning` naming the replacement at call time, **and** records
the deprecation in a process-wide registry that the upgrade drift report
(`agentforge upgrade --notes`) reads. So a consumer learns which seam they
worked around is now retired without having to exercise it or re-read
source.

No framework seams are deprecated yet — this ships the machinery and the
report seam. When a real seam is deprecated, decorate it with
`@deprecated(...)` and make sure its defining module is imported (e.g.
from `agentforge/__init__.py`) so the registry is complete for an offline
report.
"""

from __future__ import annotations

import functools
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar, cast

_F = TypeVar("_F", bound=Callable[..., object])


@dataclass(frozen=True)
class Deprecation:
    """A retired seam and the API that replaces it."""

    qualname: str
    since: str
    replacement: str
    ref: str

    def message(self) -> str:
        return (
            f"{self.qualname} is deprecated since {self.since}; "
            f"use {self.replacement} instead ({self.ref})."
        )


_REGISTRY: dict[str, Deprecation] = {}


def deprecated(*, since: str, replacement: str, ref: str) -> Callable[[_F], _F]:
    """Mark a callable deprecated — warn at call time, register for the report.

    Args:
        since: version the deprecation took effect (e.g. ``"0.4"``).
        replacement: the API to use instead (human-readable).
        ref: the spec / issue id that justifies it (e.g. ``"enh-006"``).

    The wrapped callable behaves identically except it raises a
    `DeprecationWarning` (silent for end users by default; visible under
    `-W` / pytest) before delegating.
    """

    def decorate(func: _F) -> _F:
        dep = Deprecation(
            qualname=func.__qualname__,
            since=since,
            replacement=replacement,
            ref=ref,
        )
        _REGISTRY[dep.qualname] = dep

        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> object:
            warnings.warn(dep.message(), DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        return cast("_F", wrapper)

    return decorate


def iter_deprecations() -> list[Deprecation]:
    """Every registered deprecation, sorted by ``(since, qualname)``.

    A deprecation is present only once its defining module has been
    imported; the offline notes report imports the framework first so the
    list reflects every seam decorated at import time.
    """
    return sorted(_REGISTRY.values(), key=lambda d: (d.since, d.qualname))


__all__ = ["Deprecation", "deprecated", "iter_deprecations"]
