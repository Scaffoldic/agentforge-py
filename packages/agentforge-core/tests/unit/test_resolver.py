"""Unit tests for the in-process resolver and `parse_model_string`."""

from __future__ import annotations

import pytest
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import (
    Resolver,
    parse_model_string,
    register,
    register_embedding_provider,
    register_provider,
)


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
    """The @register decorator targets the global resolver. Use a
    unique name and avoid clearing the global — clearing would nuke
    other modules' registrations (e.g. ReActLoop registers itself at
    import time)."""
    unique_name = f"decorator-test-{id(object())}"

    @register("strategies", unique_name)
    class _MyStrategy:
        pass

    try:
        cls = Resolver.global_().resolve("strategies", unique_name)
        assert cls is _MyStrategy
    finally:
        # Tidy up: remove only our own entry, never clear the global.
        # The Resolver doesn't expose a public "unregister", so we
        # poke the internal map. Tests-only access pattern.
        Resolver.global_()._registry.pop(("strategies", unique_name), None)


# ---- register_provider / register_embedding_provider ----


def test_register_provider_targets_providers_category() -> None:
    """`register_provider("name")` puts the class under
    `("providers", "name")` so `Agent` can look it up after parsing
    `"name:model-id"`."""
    unique_name = f"prov-{id(object())}"

    @register_provider(unique_name)
    class _FakeProvider:
        pass

    try:
        cls = Resolver.global_().resolve("providers", unique_name)
        assert cls is _FakeProvider
    finally:
        Resolver.global_()._registry.pop(("providers", unique_name), None)


def test_register_embedding_provider_targets_embeddings_category() -> None:
    """Embedding providers register under `("embeddings", "name")` so
    they don't collide with chat-model providers of the same name."""
    unique_name = f"emb-{id(object())}"

    @register_embedding_provider(unique_name)
    class _FakeEmbedder:
        pass

    try:
        cls = Resolver.global_().resolve("embeddings", unique_name)
        assert cls is _FakeEmbedder
    finally:
        Resolver.global_()._registry.pop(("embeddings", unique_name), None)


def test_chat_and_embedding_providers_can_share_a_name() -> None:
    """A single provider package may register both a chat client and
    an embedding client under the same name — they live in different
    categories, so no collision."""
    unique_name = f"shared-{id(object())}"

    @register_provider(unique_name)
    class _Chat:
        pass

    @register_embedding_provider(unique_name)
    class _Emb:
        pass

    try:
        assert Resolver.global_().resolve("providers", unique_name) is _Chat
        assert Resolver.global_().resolve("embeddings", unique_name) is _Emb
    finally:
        Resolver.global_()._registry.pop(("providers", unique_name), None)
        Resolver.global_()._registry.pop(("embeddings", unique_name), None)
