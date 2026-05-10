"""Default tools shipped with `agentforge` (feat-004).

Public surface — pre-built `Tool` instances ready to pass into
`Agent(tools=[...])`. Implementations live under
`agentforge._tools/`; this module re-exports them.

```python
from agentforge import Agent
from agentforge.tools import calculator, file_read

agent = Agent(model="...", tools=[calculator, file_read])
```

For tools that take configuration (e.g., `FileReadTool` with a
custom sandbox and size cap), import the class directly:

```python
from agentforge.tools import FileReadTool

custom = FileReadTool(work_dir="/srv/data", max_bytes=10_485_760)
agent = Agent(model="...", tools=[custom])
```
"""

from __future__ import annotations

from agentforge._tools.calculator import calculator
from agentforge._tools.file_read import FileReadTool, file_read

__all__ = [
    "FileReadTool",
    "calculator",
    "file_read",
]
