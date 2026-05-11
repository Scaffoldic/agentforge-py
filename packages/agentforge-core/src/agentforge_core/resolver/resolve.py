"""In-process module registry + model-string parsing.

feat-010 will extend `Resolver` to scan `importlib.metadata` entry
points; until then, anything in this registry was put there by an
explicit `register(...)` call. The two-phase design lets us write
integration tests in feat-001 without entry-point machinery.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver.discover import (
    ensure_discovered,
    module_info_for,
)

if TYPE_CHECKING:
    from agentforge_core.values.module import ModuleInfo

T = TypeVar("T", bound=type)


class Resolver:
    """Maps `(category, name) -> registered class`.

    A single global instance is shared by `register()` and `Agent`.
    Tests reset it via `Resolver.global_().clear()`.
    """

    def __init__(self) -> None:
        self._registry: dict[tuple[str, str], type] = {}

    @classmethod
    def global_(cls) -> Resolver:
        global _GLOBAL_RESOLVER  # noqa: PLW0603 — singleton intentional
        if _GLOBAL_RESOLVER is None:
            _GLOBAL_RESOLVER = cls()
        return _GLOBAL_RESOLVER

    def register(self, category: str, name: str, cls: type) -> None:
        key = (category, name)
        if key in self._registry and self._registry[key] is not cls:
            raise ModuleError(
                f"Cannot register {cls.__name__} as {category}:{name}; "
                f"already registered to {self._registry[key].__name__}."
            )
        self._registry[key] = cls

    def resolve(self, category: str, name: str) -> type:
        # Lazy entry-point discovery (feat-010): the first call to
        # `resolve()` triggers a one-shot scan of installed
        # `agentforge.*` entry points so packages-by-pip-install are
        # available without explicit imports.
        ensure_discovered(self)
        key = (category, name)
        if key not in self._registry:
            available = sorted(n for c, n in self._registry if c == category)
            raise ModuleError(
                f"No module registered for {category}:{name!r}. "
                f"Registered {category}: {available or '(none)'}. "
                f"Install the relevant agentforge-* package or register "
                f"a custom class with @register('{category}', '{name}')."
            )
        return self._registry[key]

    def list_(self, category: str | None = None) -> list[tuple[str, str, type]]:
        ensure_discovered(self)
        items = [(c, n, cls) for (c, n), cls in self._registry.items()]
        if category is not None:
            items = [item for item in items if item[0] == category]
        return sorted(items, key=lambda item: (item[0], item[1]))

    def list_installed(self, category: str | None = None) -> list[ModuleInfo]:
        """Return `ModuleInfo` for every registered module (feat-010).

        Triggers entry-point discovery first so the returned list
        reflects every `agentforge-*` package pip-installed in the
        active environment plus anything registered manually via
        `@register`.
        """
        ensure_discovered(self)
        items: list[ModuleInfo] = []
        for (cat, name), cls in self._registry.items():
            if category is not None and cat != category:
                continue
            items.append(module_info_for(cat, name, cls))
        return sorted(items, key=lambda m: (m.category, m.name))

    def clear(self) -> None:
        """Empty the in-process registry.

        Does NOT reset the entry-point discovery cache — call
        `reset_discovery()` separately if you need a fresh scan on
        the next `resolve()`. Typical tests want a clean slate
        without re-triggering discovery; tests that install fake
        entry points opt in to the rediscovery explicitly.
        """
        self._registry.clear()


_GLOBAL_RESOLVER: Resolver | None = None


def register(category: str, name: str) -> Callable[[T], T]:
    """Decorator: register a class under `(category, name)` in the global resolver.

    Example:
        @register("strategies", "my-loop")
        class MyLoop(ReasoningStrategy):
            ...
    """

    def decorator(cls: T) -> T:
        Resolver.global_().register(category, name, cls)
        return cls

    return decorator


def register_provider(name: str) -> Callable[[T], T]:
    """Decorator: register an `LLMClient` subclass as a model provider.

    Convenience wrapper around `register("providers", name)` — used by
    every concrete provider package (`agentforge-bedrock`,
    `agentforge-anthropic`, ...). The provider name corresponds to the
    leading token in a model string: `register_provider("bedrock")`
    enables `Agent(model="bedrock:...")`.

    Example:
        @register_provider("bedrock")
        class BedrockClient(LLMClient):
            def __init__(self, *, model_id: str, region: str = "us-east-1") -> None:
                ...
    """
    return register("providers", name)


def register_embedding_provider(name: str) -> Callable[[T], T]:
    """Decorator: register an `EmbeddingClient` subclass as an embedding provider.

    Mirrors `register_provider` but under the `"embeddings"` category
    so chat models and embedding models can share a provider name
    without colliding (e.g. `bedrock:anthropic.claude-...` for chat,
    `embeddings:bedrock:amazon.titan-embed-text-v2:0` for embeddings).
    """
    return register("embeddings", name)


def parse_model_string(model_str: str) -> tuple[str, str]:
    """Parse `"<provider>:<model_id>"` into `(provider, model_id)`.

    Raises:
        ModuleError: if the string does not contain a `:`.
    """
    if ":" not in model_str:
        raise ModuleError(
            f"Invalid model string {model_str!r}: expected '<provider>:<model_id>' "
            f"(for example, 'anthropic:claude-sonnet-4.7')."
        )
    provider, _, model_id = model_str.partition(":")
    if not provider or not model_id:
        raise ModuleError(
            f"Invalid model string {model_str!r}: provider and model_id must both be non-empty."
        )
    return provider, model_id
