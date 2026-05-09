"""Unit tests for the in-process resolver and `parse_model_string`."""

from __future__ import annotations

import pytest
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import Resolver, parse_model_string, register


@pytest.fixture
def resolver() -> Resolver:
    return Resolver()


# ---- parse_model_string ----


def test_parse_model_string_basic() -> None:
    assert parse_model_string("anthropic:claude-sonnet-4.7") == (
        "anthropic",
        "claude-sonnet-4.7",
    )


def test_parse_model_string_keeps_subsequent_colons() -> None:
    """Only the first ':' splits — provider IDs may contain colons."""
    p, m = parse_model_string("bedrock:us-east-1:anthropic.claude-sonnet")
    assert p == "bedrock"
    assert m == "us-east-1:anthropic.claude-sonnet"


def test_parse_model_string_no_colon_raises() -> None:
    with pytest.raises(ModuleError, match="expected '<provider>:<model_id>'"):
        parse_model_string("just-a-name")


def test_parse_model_string_empty_provider_raises() -> None:
    with pytest.raises(ModuleError, match="non-empty"):
        parse_model_string(":model")


def test_parse_model_string_empty_model_raises() -> None:
    with pytest.raises(ModuleError, match="non-empty"):
        parse_model_string("provider:")


# ---- Resolver instance ----


def test_register_and_resolve(resolver: Resolver) -> None:
    class A:
        pass

    resolver.register("strategies", "a", A)
    assert resolver.resolve("strategies", "a") is A


def test_resolve_unknown_raises_with_helpful_message(
    resolver: Resolver,
) -> None:
    with pytest.raises(ModuleError, match="No module registered"):
        resolver.resolve("strategies", "nothing")


def test_resolve_unknown_lists_available(resolver: Resolver) -> None:
    class A:
        pass

    resolver.register("strategies", "alpha", A)
    with pytest.raises(ModuleError, match=r"alpha"):
        resolver.resolve("strategies", "beta")


def test_register_same_class_twice_is_idempotent(resolver: Resolver) -> None:
    class A:
        pass

    resolver.register("strategies", "a", A)
    resolver.register("strategies", "a", A)
    assert resolver.resolve("strategies", "a") is A


def test_register_different_class_under_same_name_raises(
    resolver: Resolver,
) -> None:
    class A:
        pass

    class B:
        pass

    resolver.register("strategies", "a", A)
    with pytest.raises(ModuleError, match="already registered"):
        resolver.register("strategies", "a", B)


def test_list_filters_by_category(resolver: Resolver) -> None:
    class A:
        pass

    class B:
        pass

    resolver.register("strategies", "a", A)
    resolver.register("memory", "b", B)
    assert {n for _, n, _ in resolver.list_("strategies")} == {"a"}
    assert {n for _, n, _ in resolver.list_("memory")} == {"b"}
    assert len(resolver.list_()) == 2


def test_clear_empties_registry(resolver: Resolver) -> None:
    class A:
        pass

    resolver.register("strategies", "a", A)
    resolver.clear()
    assert resolver.list_() == []


# ---- Global resolver and decorator ----


def test_global_resolver_is_singleton() -> None:
    a = Resolver.global_()
    b = Resolver.global_()
    assert a is b


def test_register_decorator_uses_global() -> None:
    Resolver.global_().clear()

    @register("strategies", "decorator-test")
    class _MyStrategy:
        pass

    cls = Resolver.global_().resolve("strategies", "decorator-test")
    assert cls is _MyStrategy
    Resolver.global_().clear()
