"""Module resolver — maps name → registered class.

Per ADR-0004, modules normally register via Python entry points
(loaded by feat-010). For feat-001 we ship the in-process registry
that the entry-point loader will populate. Anyone can register a
class manually with `@register("strategies", "my-loop")` for an
in-repo or test-only module.

A model identifier string `"<provider>:<model_id>"` is parsed by
`parse_model_string`; the leading provider is looked up as an entry
in `agentforge.providers`, the trailing piece is treated as the
model id and passed through to the provider constructor (per
feat-003).
"""

from __future__ import annotations

from agentforge_core.resolver.resolve import (
    Resolver,
    parse_model_string,
    register,
    register_embedding_provider,
    register_provider,
)

__all__ = [
    "Resolver",
    "parse_model_string",
    "register",
    "register_embedding_provider",
    "register_provider",
]
