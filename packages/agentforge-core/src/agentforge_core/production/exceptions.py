"""AgentForge exception hierarchy.

Every exception the framework raises is a subclass of `AgentForgeError`.
This is the only place new top-level exception classes are defined; per
.claude/standards/coding.md, modules subclass these for their own
errors but never `raise Exception(...)`.
"""

from __future__ import annotations


class AgentForgeError(Exception):
    """Base exception for all AgentForge errors.

    Catch this to handle any framework-raised error generically.
    Production code should narrow to a more specific subclass.
    """


# Locked names per the framework's public API; suppress N818 globally
# in this file so individual classes don't need per-line noqa.
# ruff: noqa: N818


class BudgetExceeded(AgentForgeError):
    """Raised when `BudgetPolicy.check` detects a USD or token cap breach.

    The agent run terminates immediately; partial state is preserved on
    `RunResult`.
    """


class GuardrailViolation(AgentForgeError):
    """Raised when a non-budget guardrail trips.

    Examples: iteration cap reached, error streak limit hit. Distinct
    from `BudgetExceeded` so callers can branch on the cause.
    """


class ModuleError(AgentForgeError):
    """Raised at agent construction when the resolver cannot find a
    registered module by name.

    Surfaced at startup (P11 — fail at startup, not at runtime), with a
    clear message telling the developer which package to install or
    which entry point is missing.
    """


class ProviderError(AgentForgeError):
    """Base for errors originating in an LLM / embedding provider.

    Concrete subclasses (`RateLimitError`, etc.) ship in feat-003 with
    the provider abstraction.
    """


class CapabilityNotSupported(AgentForgeError):
    """Raised when an optional capability is invoked on a driver that
    does not declare it.

    Per ADR-0009, capability negotiation is honest — drivers declare
    their supported set and this exception fires if a consumer skipped
    the `supports(...)` check.
    """
