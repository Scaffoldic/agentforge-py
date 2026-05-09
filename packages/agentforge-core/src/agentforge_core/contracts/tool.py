"""`Tool` — the locked tool ABC.

feat-001 ships the explicit-`input_schema` form. feat-004 layers a
`@tool` decorator on top that infers the schema from a typed function's
signature; the resulting object is still a `Tool` subclass under the
hood.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from agentforge_core.values.messages import ToolSpec


class Tool(ABC):
    """A typed callable the agent can invoke.

    Subclasses declare three class attributes:

        name: str                   — unique identifier the LLM sees
        description: str            — human-readable usage description
        input_schema: type[BaseModel]
                                    — Pydantic v2 model for inputs

    Plus override `run`. The decorator-based path in feat-004 builds
    these attributes automatically from a typed function.
    """

    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[type[BaseModel]]
    capabilities: ClassVar[frozenset[str]] = frozenset()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        # Concrete subclasses must declare the three class attributes.
        for attr in ("name", "description", "input_schema"):
            if attr not in cls.__dict__ and not _inherited_attr(cls, attr):
                raise TypeError(
                    f"{cls.__name__} must declare class attribute '{attr}' (see Tool docstring)."
                )

    @abstractmethod
    async def run(self, **kwargs: Any) -> Any:
        """Execute the tool with kwargs validated against `input_schema`."""

    def to_spec(self) -> ToolSpec:
        """Provider-agnostic JSON-schema description for the LLM."""
        return ToolSpec(
            name=type(self).name,
            description=type(self).description,
            schema=type(self).input_schema.model_json_schema(),
        )


def _inherited_attr(cls: type, attr: str) -> bool:
    """Walk the MRO (excluding `cls` itself and the abstract `Tool`)
    looking for a non-`Tool` ancestor that declared `attr`."""
    for base in cls.__mro__[1:]:
        if base is Tool or base is object:
            continue
        if attr in base.__dict__:
            return True
    return False
