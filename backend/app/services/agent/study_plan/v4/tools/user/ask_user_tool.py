"""Ask user tool."""

import logging
from typing import Any

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)


class AskUserTool(BaseTool):
    """Ask user for input or clarification.

    Used when the agent needs human guidance.
    """

    @property
    def name(self) -> str:
        return "ask_user"

    @property
    def description(self) -> str:
        return (
            "Ask the user for input or clarification. "
            "Use when you need guidance on experimental choices, "
            "clarification on requirements, or cannot proceed automatically. "
            "HIGH COST - only use when necessary."
        )

    @property
    def cost(self) -> float:
        return 0.9  # High cost (user waiting)

    @property
    def category(self) -> str:
        return "user"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="question",
                type="str",
                description="Question to ask the user",
                required=True,
            ),
            ToolParameter(
                name="options",
                type="list",
                description="List of options for user to choose from",
                required=False,
                default=[],
            ),
        ]

    async def run(
        self,
        question: str,
        options: list | None = None,
    ) -> dict[str, Any]:
        """Ask user for input.

        Note: In streaming mode, this yields an event for the UI.
        In sync mode, it returns a placeholder response.

        Args:
            question: Question to ask
            options: Optional list of choices

        Returns:
            Dict indicating user input is needed
        """
        logger.info(f"Asking user: {question}")

        return {
            "requires_user_input": True,
            "question": question,
            "options": options or [],
            "answer": None,  # Will be filled by user
        }
