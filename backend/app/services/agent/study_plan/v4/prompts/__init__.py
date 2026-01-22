"""Prompts for v4 agent."""

from app.services.agent.study_plan.v4.prompts.reasoning import (
    TOOL_SELECTION_PROMPT,
    ALTERNATIVE_SELECTION_PROMPT,
)
from app.services.agent.study_plan.v4.prompts.recovery import (
    RECOVERY_STRATEGY_PROMPT,
)

__all__ = [
    "TOOL_SELECTION_PROMPT",
    "ALTERNATIVE_SELECTION_PROMPT",
    "RECOVERY_STRATEGY_PROMPT",
]
