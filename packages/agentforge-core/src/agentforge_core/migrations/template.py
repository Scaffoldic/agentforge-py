"""Migration body templating (feat-024 v0.3 follow-up).

Per-driver migrators may need per-deployment variables in their
migration bodies — Postgres `vector(${dimensions})` and SurrealDB
`HNSW DIMENSION ${dimensions}` are the canonical cases. The
templating syntax is Python's :class:`string.Template` with
``${var}`` placeholders and ``$$`` for a literal ``$``.

Important invariant: the migration's checksum is computed over the
*un-substituted* template body. Re-deploying with a different
variable value (e.g. swapping a 768-dim embedder for a 1536-dim
one) produces the same checksum, so the framework's drift
detection stays correct.

Unknown placeholders left untouched (`safe_substitute` semantics)
— template-key typos surface as SQL syntax errors at apply time
rather than silently empty replacements.
"""

from __future__ import annotations

from string import Template


def render_migration_up(body: str, variables: dict[str, str] | None) -> str:
    """Substitute ``${var}`` placeholders in ``body`` with ``variables``.

    Returns ``body`` unchanged when ``variables`` is ``None`` or
    empty. Unknown placeholders pass through unchanged so callers
    can spot template-key typos as apply-time SQL errors.
    """
    if not variables:
        return body
    return Template(body).safe_substitute(**variables)
