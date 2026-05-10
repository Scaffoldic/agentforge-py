"""`calculator` — arithmetic expression tool (feat-004).

Evaluates pure-arithmetic expressions via Python's AST module
(`ast.parse` + recursive walker). **Does not use `eval()`** — only a
closed set of node types is allowed, so the tool can't be tricked
into running arbitrary Python.

Supported:
  - Numeric literals (int, float)
  - Binary ops: `+`, `-`, `*`, `/`, `//`, `%`, `**`
  - Unary ops: `+`, `-`
  - Parenthesisation

Rejected (raises `ValueError`):
  - Names (variables), attribute access, function calls
  - Subscripts, list / dict / set literals
  - Comprehensions, lambdas, walrus, anything statement-y

Capabilities: empty (pure computation, no side effects).
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable

from agentforge._tools.decorator import tool

_Number = int | float
_BinaryFn = Callable[[_Number, _Number], _Number]
_UnaryFn = Callable[[_Number], _Number]

_BINARY_OPS: dict[type[ast.operator], _BinaryFn] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type[ast.unaryop], _UnaryFn] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _evaluate(node: ast.AST) -> _Number:
    """Walk an AST node, evaluating only the closed set of allowed
    arithmetic node types. Raise `ValueError` on anything else."""
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        msg = f"calculator: literal {node.value!r} is not a number"
        raise ValueError(msg)
    if isinstance(node, ast.BinOp):
        bop_type = type(node.op)
        bop_fn = _BINARY_OPS.get(bop_type)
        if bop_fn is None:
            msg = f"calculator: binary operator {bop_type.__name__!r} not allowed"
            raise ValueError(msg)
        return bop_fn(_evaluate(node.left), _evaluate(node.right))
    if isinstance(node, ast.UnaryOp):
        uop_type = type(node.op)
        uop_fn = _UNARY_OPS.get(uop_type)
        if uop_fn is None:
            msg = f"calculator: unary operator {uop_type.__name__!r} not allowed"
            raise ValueError(msg)
        return uop_fn(_evaluate(node.operand))
    msg = f"calculator: AST node {type(node).__name__!r} not allowed"
    raise ValueError(msg)


@tool
def calculator(expression: str) -> float:
    """Evaluate an arithmetic expression and return the result.

    Supports `+`, `-`, `*`, `/`, `//`, `%`, `**` and parentheses.
    Variables, function calls, and any non-arithmetic syntax are
    rejected — this is a calculator, not a Python interpreter.

    Args:
        expression: The arithmetic expression to evaluate, e.g.
            `"(1 + 2) * 3"` or `"2 ** 10"`.

    Returns:
        The numeric result as a float (int values are coerced to
        float for a uniform return type).
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        msg = f"calculator: cannot parse expression {expression!r}: {exc.msg}"
        raise ValueError(msg) from exc
    result = _evaluate(tree)
    return float(result)


__all__ = ["calculator"]
