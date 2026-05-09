"""Map botocore / aiobotocore exceptions to AgentForge `ProviderError` subclasses.

botocore raises `ClientError` for every failed AWS API call with the
service-specific code in `error.response["Error"]["Code"]`. We branch
on that code rather than the exception class so the mapping stays
correct as botocore evolves.

Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting-api-error-codes.html
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from agentforge_core.production.exceptions import (
    AuthenticationError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    ServiceError,
    TimeoutError,
)

if TYPE_CHECKING:
    from botocore.exceptions import ClientError


# Bedrock + Bedrock Runtime error codes that mean the request was throttled.
_THROTTLING_CODES = frozenset(
    {
        "ThrottlingException",
        "TooManyRequestsException",
        "ProvisionedThroughputExceededException",
        "ModelTimeoutException",  # surfaced when a hosted model is overloaded
    }
)

_AUTH_CODES = frozenset(
    {
        "AccessDeniedException",
        "UnauthorizedException",
        "ExpiredTokenException",
        "InvalidSignatureException",
        "MissingAuthenticationTokenException",
    }
)

_NOT_FOUND_CODES = frozenset(
    {
        "ResourceNotFoundException",
        "ModelNotReadyException",
    }
)

_SERVICE_ERROR_CODES = frozenset(
    {
        "InternalServerException",
        "ServiceUnavailableException",
        "ModelErrorException",
        "ModelStreamErrorException",
    }
)

# HTTP status thresholds for the fallback-by-status branch.
_HTTP_STATUS_TOO_MANY_REQUESTS = 429
_HTTP_STATUS_UNAUTHORIZED = 401
_HTTP_STATUS_FORBIDDEN = 403
_HTTP_STATUS_SERVER_ERROR_MIN = 500
_HTTP_STATUS_SERVER_ERROR_MAX = 600

# Mapping from code-family -> (exception, message-prefix). The order
# of insertion matters when families overlap; today they don't.
_CODE_FAMILIES: tuple[tuple[frozenset[str], type[ProviderError], str], ...] = (
    (_THROTTLING_CODES, RateLimitError, "throttled"),
    (_AUTH_CODES, AuthenticationError, "auth failed"),
    (_NOT_FOUND_CODES, ModelNotFoundError, "model not found"),
    (_SERVICE_ERROR_CODES, ServiceError, "service error"),
)


def _classify_known_code(code: str, message: str) -> ProviderError | None:
    """Return the mapped error for a known service-specific code, or
    `None` if the code is not in our recognised tables."""
    if code == "ValidationException":
        if "model" in message.lower() or "modelId" in message:
            return ModelNotFoundError(f"Bedrock validation: {message}")
        return ProviderError(f"Bedrock validation: {message}")
    for family, exc_type, prefix in _CODE_FAMILIES:
        if code in family:
            return exc_type(f"Bedrock {prefix} ({code}): {message}")
    return None


def _classify_by_http_status(status: int, code: str, message: str) -> ProviderError | None:
    """Fallback when the service-specific code is unrecognised — branch
    on HTTP status. Returns `None` for status codes outside the cases
    we handle (callers fall through to a generic `ProviderError`)."""
    suffix = f"{code or 'unknown'}: {message}"
    if _HTTP_STATUS_SERVER_ERROR_MIN <= status < _HTTP_STATUS_SERVER_ERROR_MAX:
        return ServiceError(f"Bedrock {status} {suffix}")
    if status == _HTTP_STATUS_TOO_MANY_REQUESTS:
        return RateLimitError(f"Bedrock {status} {suffix}")
    if status in (_HTTP_STATUS_UNAUTHORIZED, _HTTP_STATUS_FORBIDDEN):
        return AuthenticationError(f"Bedrock {status} {suffix}")
    return None


def map_client_error(exc: ClientError) -> ProviderError:
    """Convert a botocore `ClientError` into the matching `ProviderError`.

    Falls back to a generic `ProviderError` for unrecognised codes —
    keeps the run failing loudly rather than swallowing silently, but
    with the framework's exception type so callers can still catch
    `ProviderError`.
    """
    response = getattr(exc, "response", None) or {}
    err = response.get("Error", {}) if isinstance(response, dict) else {}
    code = err.get("Code", "")
    message = err.get("Message", str(exc))

    by_code = _classify_known_code(code, message)
    if by_code is not None:
        return by_code

    status = (
        response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if isinstance(response, dict)
        else None
    )
    if isinstance(status, int):
        by_status = _classify_by_http_status(status, code, message)
        if by_status is not None:
            return by_status

    return ProviderError(f"Bedrock {code or 'error'}: {message}")


def map_unexpected(exc: BaseException) -> ProviderError:
    """Map a non-`ClientError` exception (timeouts, network errors).

    Bedrock SDKs raise `asyncio.TimeoutError` / `botocore.exceptions.ReadTimeoutError`
    on configured-timeout breaches; everything else is surfaced as
    a generic `ProviderError`.
    """
    name = type(exc).__name__
    if isinstance(exc, asyncio.TimeoutError) or "Timeout" in name:
        return TimeoutError(f"Bedrock request timed out: {exc}")
    return ProviderError(f"Bedrock {name}: {exc}")


def is_retryable(exc: ProviderError) -> bool:
    """`True` if the strategy should retry after backoff."""
    return isinstance(exc, (RateLimitError, ServiceError, TimeoutError))
