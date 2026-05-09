"""Unit tests for the Bedrock error mapper."""

from __future__ import annotations

import builtins

import pytest
from agentforge_bedrock._errors import is_retryable, map_client_error, map_unexpected
from agentforge_core.production.exceptions import (
    AuthenticationError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    ServiceError,
    TimeoutError,
)
from botocore.exceptions import ClientError


def _err(code: str, message: str = "boom", status: int | None = None) -> ClientError:
    response: dict[str, object] = {"Error": {"Code": code, "Message": message}}
    if status is not None:
        response["ResponseMetadata"] = {"HTTPStatusCode": status}
    return ClientError(error_response=response, operation_name="Converse")


@pytest.mark.parametrize(
    "code",
    ["ThrottlingException", "TooManyRequestsException", "ProvisionedThroughputExceededException"],
)
def test_throttling_codes_map_to_rate_limit_error(code: str) -> None:
    assert isinstance(map_client_error(_err(code)), RateLimitError)


@pytest.mark.parametrize(
    "code",
    ["AccessDeniedException", "UnauthorizedException", "ExpiredTokenException"],
)
def test_auth_codes_map_to_authentication_error(code: str) -> None:
    assert isinstance(map_client_error(_err(code)), AuthenticationError)


@pytest.mark.parametrize(
    "code",
    ["ResourceNotFoundException", "ModelNotReadyException"],
)
def test_not_found_codes_map_to_model_not_found_error(code: str) -> None:
    assert isinstance(map_client_error(_err(code)), ModelNotFoundError)


@pytest.mark.parametrize(
    "code",
    ["InternalServerException", "ServiceUnavailableException", "ModelErrorException"],
)
def test_service_codes_map_to_service_error(code: str) -> None:
    assert isinstance(map_client_error(_err(code)), ServiceError)


def test_validation_with_model_in_message_maps_to_model_not_found() -> None:
    err = _err("ValidationException", "Invalid modelId provided")
    assert isinstance(map_client_error(err), ModelNotFoundError)


def test_validation_without_model_keyword_maps_to_provider_error() -> None:
    err = _err("ValidationException", "request payload too large")
    mapped = map_client_error(err)
    assert isinstance(mapped, ProviderError)
    assert not isinstance(mapped, ModelNotFoundError)


def test_unknown_code_with_5xx_status_maps_to_service_error() -> None:
    err = _err("WeirdNew", status=503)
    assert isinstance(map_client_error(err), ServiceError)


def test_unknown_code_with_429_maps_to_rate_limit_error() -> None:
    err = _err("WeirdNew", status=429)
    assert isinstance(map_client_error(err), RateLimitError)


def test_unknown_code_with_403_maps_to_authentication_error() -> None:
    err = _err("WeirdNew", status=403)
    assert isinstance(map_client_error(err), AuthenticationError)


def test_unknown_code_no_status_maps_to_provider_error() -> None:
    mapped = map_client_error(_err("WeirdNew"))
    assert isinstance(mapped, ProviderError)
    assert not isinstance(mapped, RateLimitError | ServiceError | AuthenticationError)


def test_map_unexpected_timeout_returns_timeout_error() -> None:
    mapped = map_unexpected(builtins.TimeoutError("read timeout"))
    assert isinstance(mapped, TimeoutError)


def test_map_unexpected_random_exception_returns_provider_error() -> None:
    mapped = map_unexpected(RuntimeError("bus crash"))
    assert isinstance(mapped, ProviderError)


# ---- is_retryable ----


def test_rate_limit_is_retryable() -> None:
    assert is_retryable(RateLimitError("x"))


def test_service_error_is_retryable() -> None:
    assert is_retryable(ServiceError("x"))


def test_timeout_is_retryable() -> None:
    assert is_retryable(TimeoutError("x"))


def test_auth_error_is_not_retryable() -> None:
    assert not is_retryable(AuthenticationError("x"))


def test_model_not_found_is_not_retryable() -> None:
    assert not is_retryable(ModelNotFoundError("x"))


def test_generic_provider_error_is_not_retryable() -> None:
    assert not is_retryable(ProviderError("x"))
