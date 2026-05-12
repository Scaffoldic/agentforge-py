"""Pipeline engine + Task ABC (feat-015).

`Pipeline` runs a DAG of deterministic `Task` instances before the
agent's reasoning loop starts; their consolidated findings are
exposed to the LLM as a system-prompt addendum and via a built-in
``pipeline_findings`` tool.
"""

from __future__ import annotations

from agentforge_core.contracts.task import Task
from agentforge_core.values.pipeline import PipelineResult

from agentforge.pipeline.engine import OnTaskError, Pipeline
from agentforge.pipeline.errors import PipelineFailure
from agentforge.pipeline.tool import PipelineFindingsInput, PipelineFindingsTool

__all__ = [
    "OnTaskError",
    "Pipeline",
    "PipelineFailure",
    "PipelineFindingsInput",
    "PipelineFindingsTool",
    "PipelineResult",
    "Task",
]
