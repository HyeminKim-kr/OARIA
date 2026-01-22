"""Tools for v4 agent.

Tools are the actions the agent can take to interact with the world.
Each tool has:
- name: Unique identifier
- description: What the tool does (for LLM)
- input schema: Required parameters
- cost: Relative cost of execution
"""

from app.services.agent.study_plan.v4.tools.registry import ToolRegistry
from app.services.agent.study_plan.v4.tools.base import BaseTool

__all__ = [
    "ToolRegistry",
    "BaseTool",
]
