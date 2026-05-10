"""`@tool` — typed-function-to-`Tool` decorator (feat-004).

Wraps a typed function as a concrete `Tool` subclass:

    from agentforge import tool

    @tool
    def lookup_user(user_id: str, include_email: bool = False) -> dict:
        '''Fetch a user record.

        Args:
            user_id: The internal user id (ULID).
            include_email: When True, include the email field.

        Returns:
            A dict with name and signup_date.
        '''
        return db.get_user(user_id, with_email=include_email)

The decorator inspects the wrapped function and constructs:

  - `name`              from the function's `__name__` (or the
                        `name=` override argument).
  - `description`       from the docstring's summary line + Args
                        section, parsed Google-style. The first
                        non-blank non-arg line is the summary;
                        per-arg descriptions feed Pydantic field
                        descriptions.
  - `input_schema`      a Pydantic v2 model built from the
                        function's typed parameters. Required
                        parameters have no default; optional ones
                        carry the function's default.
  - `run(**kwargs)`     dispatches to the wrapped function (sync or
                        async). Returns whatever the function
                        returns; the dispatch path in strategies
                        validates kwargs before calling `run`.

Errors at decoration time:

  - Missing type hint on a parameter      → `ValueError`
  - Variadic args (`*args`, `**kwargs`)   → `ValueError`
  - Positional-only parameters            → `ValueError` (LLM
                                            tool calls are
                                            keyword-only over the
                                            wire)
  - `self` / class-method usage           → not supported here;
                                            subclass `Tool`
                                            directly instead

Capabilities default to empty. Pass `capabilities={"network",
"filesystem"}` to declare them up front (used by the future safety
guardrails in feat-018).
"""

from __future__ import annotations

import asyncio
import inspect
import re
from collections.abc import Callable, Iterable
from typing import Any, get_type_hints

from agentforge_core.contracts.tool import Tool
from pydantic import BaseModel, Field, create_model

# Sentinel for "no default" — distinguished from `None` (which is a
# legitimate default for `Optional[X] = None` parameters).
_NO_DEFAULT = inspect.Parameter.empty


def tool(
    fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    capabilities: Iterable[str] = (),
) -> Any:
    """Decorate a typed function as a `Tool`.

    Usage:

        @tool
        def my_func(x: int) -> str: ...

        # or with explicit options:
        @tool(name="custom_name", capabilities={"network"})
        def my_func(x: int) -> str: ...

    Returns a `Tool` *instance* (not a class). Pass the instance to
    `Agent(tools=[...])` directly.
    """
    # Bare-decorator form: `@tool` without parens.
    if fn is not None and callable(fn) and not isinstance(fn, type):
        return _build_tool(fn, name=None, description=None, capabilities=())

    # Parameterised form: `@tool(name=..., ...)` — fn is None here;
    # return a closure that takes the function on the next call.
    def _decorate(real_fn: Callable[..., Any]) -> Tool:
        return _build_tool(
            real_fn,
            name=name,
            description=description,
            capabilities=capabilities,
        )

    return _decorate


def _build_tool(
    fn: Callable[..., Any],
    *,
    name: str | None,
    description: str | None,
    capabilities: Iterable[str],
) -> Tool:
    """Synthesize a concrete `Tool` subclass and instantiate it."""
    sig = inspect.signature(fn)
    type_hints = get_type_hints(fn)

    fields = _build_pydantic_fields(fn, sig, type_hints)
    parsed_doc = _parse_google_docstring(fn.__doc__ or "")

    # Apply per-arg descriptions from the docstring's Args block by
    # wrapping each field's default in `Field(default=..., description=...)`.
    for field_name, arg_doc in parsed_doc.arg_descriptions.items():
        if field_name not in fields or not arg_doc:
            continue
        annotation, default = fields[field_name]
        if default is ...:
            fields[field_name] = (annotation, Field(..., description=arg_doc))
        else:
            fields[field_name] = (annotation, Field(default=default, description=arg_doc))

    schema_cls_name = _pascal_case(name or fn.__name__) + "Input"
    # mypy can't verify keyword unpacking against `create_model`'s
    # overloads; the runtime contract is exactly `create_model(name,
    # **{field: (annotation, default), ...})`.
    schema_cls: type[BaseModel] = create_model(schema_cls_name, **fields)  # type: ignore[call-overload]

    final_name = name or fn.__name__
    final_description = description or parsed_doc.summary or fn.__name__
    final_capabilities = frozenset(capabilities)

    is_coroutine = asyncio.iscoroutinefunction(fn)

    # Synthesize the Tool subclass dynamically. We use `type()`
    # instead of a `class ...:` block so the closure-captured
    # `schema_cls` is bound cleanly into the class namespace
    # (Python's class-body scope rules don't see enclosing locals
    # via plain `name = name` assignment shapes).
    async def _run(self: Any, **kwargs: Any) -> Any:  # noqa: ARG001 — bound method needs `self`
        if is_coroutine:
            return await fn(**kwargs)
        return fn(**kwargs)

    cls_namespace: dict[str, Any] = {
        "name": final_name,
        "description": final_description,
        "input_schema": schema_cls,
        "capabilities": final_capabilities,
        "run": _run,
    }
    decorated_cls = type(
        _pascal_case(final_name) + "Tool",
        (Tool,),
        cls_namespace,
    )
    instance: Tool = decorated_cls()
    return instance


def _build_pydantic_fields(
    fn: Callable[..., Any],
    sig: inspect.Signature,
    type_hints: dict[str, Any],
) -> dict[str, tuple[Any, Any]]:
    """Walk the function's parameters and produce `create_model`
    field definitions (annotation + default).

    Raises `ValueError` on:
      - missing type hint
      - variadic args (`*args`, `**kwargs`)
      - positional-only parameters
      - the `return` annotation slot (skipped silently — not a
        field)
    """
    fields: dict[str, tuple[Any, Any]] = {}
    for param_name, param in sig.parameters.items():
        # Disallow self / cls — decorator is for free functions.
        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            msg = (
                f"@tool: parameter {param_name!r} on {fn.__qualname__!r} is "
                "positional-only. LLM tool calls bind by keyword; declare "
                "the parameter as positional-or-keyword instead."
            )
            raise ValueError(msg)
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            msg = (
                f"@tool: variadic parameter {param_name!r} on "
                f"{fn.__qualname__!r} is not supported. Tools must declare "
                "every input explicitly so the schema is complete."
            )
            raise ValueError(msg)

        if param_name not in type_hints:
            msg = (
                f"@tool: parameter {param_name!r} on {fn.__qualname__!r} "
                "is missing a type hint. Every parameter must be typed."
            )
            raise ValueError(msg)

        annotation = type_hints[param_name]
        default = param.default if param.default is not _NO_DEFAULT else ...
        fields[param_name] = (annotation, default)
    return fields


# ----------------------------------------------------------------------
# Google-style docstring parser
# ----------------------------------------------------------------------


class _ParsedDoc(BaseModel):
    summary: str
    arg_descriptions: dict[str, str]


_ARGS_HEADER_RE = re.compile(r"^\s*Args\s*:\s*$", re.MULTILINE)
_ARG_LINE_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*(?:\(.*?\))?\s*:\s*(.*)$")
_SECTION_HEADERS = ("Returns:", "Raises:", "Yields:", "Example:", "Examples:", "Note:", "Notes:")


def _parse_google_docstring(doc: str) -> _ParsedDoc:
    """Parse a Google-style docstring.

    Extracts:
      - `summary`: the first non-blank line(s) before any section
        header.
      - `arg_descriptions`: per-arg one-line descriptions from the
        `Args:` block. Multi-line arg descriptions concatenate into
        one string.
    """
    if not doc:
        return _ParsedDoc(summary="", arg_descriptions={})

    lines = inspect.cleandoc(doc).splitlines()
    summary_lines: list[str] = []
    arg_block: list[str] = []
    in_args = False
    for line in lines:
        stripped = line.strip()
        if not in_args and _ARGS_HEADER_RE.match(line):
            in_args = True
            continue
        if in_args and any(stripped.startswith(h) for h in _SECTION_HEADERS):
            in_args = False
            continue
        if in_args:
            arg_block.append(line)
        elif stripped:
            # Stop summary if we hit a non-Args section header.
            if any(stripped.startswith(h) for h in _SECTION_HEADERS):
                break
            summary_lines.append(stripped)

    summary = " ".join(summary_lines).strip()
    args = _parse_arg_block(arg_block)
    return _ParsedDoc(summary=summary, arg_descriptions=args)


def _parse_arg_block(lines: list[str]) -> dict[str, str]:
    """Parse the body of a Google-style `Args:` block into
    `{arg_name: description}`."""
    out: dict[str, str] = {}
    current_name: str | None = None
    current_desc: list[str] = []
    for line in lines:
        m = _ARG_LINE_RE.match(line)
        if m:
            if current_name is not None:
                out[current_name] = " ".join(current_desc).strip()
            current_name = m.group(1)
            current_desc = [m.group(2).strip()]
        elif current_name is not None and line.strip():
            current_desc.append(line.strip())
    if current_name is not None:
        out[current_name] = " ".join(current_desc).strip()
    return out


def _pascal_case(s: str) -> str:
    """Convert `snake_case` or `kebab-case` to `PascalCase`."""
    parts = re.split(r"[_\-\s]+", s)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


__all__ = ["tool"]
