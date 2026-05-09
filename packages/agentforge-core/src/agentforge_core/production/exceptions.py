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

    Concrete subclasses below cover the cross-provider failure modes
    every reasoning loop needs to branch on. Provider drivers map
    their SDK exceptions into one of these at the boundary; callers
    catch `ProviderError` for general handling or narrow to a
    specific subclass for retry / surfacing logic.
    """


class RateLimitError(ProviderError):
    """The provider throttled the request (HTTP 429 / `ThrottlingException`).

    Retryable with exponential backoff. Provider drivers honour
    `Retry-After` headers when present.
    """


class AuthenticationError(ProviderError):
    """The provider rejected credentials (HTTP 401 / 403).

    Not retryable. The agent run terminates and the developer fixes
    credentials at the deployment layer.
    """


class ModelNotFoundError(ProviderError):
    """The provider does not recognise the requested model id.

    Surfaced at the first call rather than at construction because
    most providers don't expose a synchronous "does this model exist"
    check. Not retryable.
    """


class ServiceError(ProviderError):
    """The provider returned a transient server error (HTTP 5xx).

    Retryable. Drivers retry up to `max_retries` times with bounded
    exponential backoff before propagating.
    """


class TimeoutError(ProviderError):
    """A request to the provider exceeded the configured timeout.

    Distinct from the stdlib `TimeoutError` (which subclasses
    `OSError`); this one subclasses `ProviderError` so it can be
    caught by the same handler as other provider failures. Retryable.
    """


class CapabilityNotSupported(AgentForgeError):
    """Raised when an optional capability is invoked on a driver that
    does not declare it.

    Per ADR-0009, capability negotiation is honest — drivers declare
    their supported set and this exception fires if a consumer skipped
    the `supports(...)` check.
    """
