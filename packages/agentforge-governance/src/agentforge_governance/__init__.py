"""AgentForge — governance spine drivers.

The contracts live in `agentforge-core`; this package ships the
default, offline, zero-dependency drivers for each governance pillar.

feat-029 ships the identity pillar (`LocalIdentityProvider`); registry,
policy, and audit drivers land here as their pillars ship.
"""

from __future__ import annotations

# Version is sourced from the installed distribution metadata so it can
# never drift from pyproject.toml (bug-024).
from importlib.metadata import PackageNotFoundError as _PkgNotFound
from importlib.metadata import version as _dist_version

from agentforge_governance.identity.local import LocalIdentityProvider

try:
    __version__ = _dist_version("agentforge-governance")
except _PkgNotFound:  # pragma: no cover - source tree without installed metadata
    __version__ = "0.0.0+unknown"

__all__ = [
    "LocalIdentityProvider",
    "__version__",
]
