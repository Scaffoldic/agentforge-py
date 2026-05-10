"""Internal tooling module (feat-004).

The `@tool` decorator and the four shipped default tools
(`calculator`, `file_read`, `web_search`, `shell`) live under this
underscore-prefixed package; the public surface is re-exported from
`agentforge` (`from agentforge import tool`) and from
`agentforge.tools` (`from agentforge.tools import calculator`).
"""

from __future__ import annotations

from agentforge._tools.decorator import tool

__all__ = ["tool"]
