"""{{ project_name }}: {{ description }}"""

from {{ project_slug | replace('-', '_') }}.main import run_agent

__all__ = ["run_agent"]
