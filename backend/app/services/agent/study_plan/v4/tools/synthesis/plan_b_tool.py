"""Generate Plan B tool."""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)

PLAN_B_PROMPT = """Create an alternative research plan (Plan B) that addresses resource constraints.

Original Plan (Plan A):
{plan_a}

Constraints:
{constraints}

Create Plan B that:
1. Achieves the same scientific goals with limited resources
2. Uses simpler/cheaper methods where possible
3. Prioritizes essential experiments
4. Identifies acceptable tradeoffs

Format in Markdown with clear comparison to Plan A.
"""


class GeneratePlanBTool(BaseTool):
    """Generate alternative Plan B.

    Creates a resource-conscious alternative to Plan A.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "generate_plan_b"

    @property
    def description(self) -> str:
        return (
            "Generate an alternative Plan B that considers resource constraints. "
            "Creates a simpler/cheaper version of Plan A while maintaining "
            "scientific validity. Use when Plan A may be too resource-intensive."
        )

    @property
    def cost(self) -> float:
        return 0.5

    @property
    def category(self) -> str:
        return "synthesis"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="plan_a",
                type="dict",
                description="Original plan (Plan A) to create alternative for",
                required=True,
            ),
            ToolParameter(
                name="constraints",
                type="list",
                description="Constraints to address in Plan B",
                required=False,
                default=[],
            ),
        ]

    async def run(
        self,
        plan_a: dict,
        constraints: list | None = None,
    ) -> dict[str, Any]:
        """Generate Plan B.

        Args:
            plan_a: Original plan
            constraints: Resource constraints

        Returns:
            Dict with plan_b and tradeoffs
        """
        logger.info("Generating Plan B...")

        try:
            from app.services.agent.study_plan.nodes.synthesize_plan_v3 import (
                generate_plan_b,
            )

            result = await generate_plan_b(
                plan_a=plan_a,
                constraints=constraints or [],
            )
            return result

        except ImportError:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.2,
                )

            plan_a_text = plan_a.get("plan", str(plan_a))
            constraints_text = "\n".join([
                f"- {c}" for c in (constraints or ["Limited budget", "Time constraints"])
            ])

            prompt = PLAN_B_PROMPT.format(
                plan_a=plan_a_text,
                constraints=constraints_text,
            )
            response = await self._llm.ainvoke(prompt)

            return {
                "plan_b": response.content,
                "tradeoffs": [
                    "Reduced experimental scope",
                    "Simpler methodology",
                    "Potentially lower statistical power",
                ],
            }
