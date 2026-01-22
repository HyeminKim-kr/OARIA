"""Suggest measurements tool."""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)

MEASUREMENTS_PROMPT = """Suggest measurement variables and assays for this experiment.

Experiment:
{experiment}

Hypothesis Variables:
{hypothesis_vars}

For each hypothesis variable, suggest:
1. How to measure it
2. What assay/technique to use
3. Units and expected ranges

Respond in JSON:
{{
    "measurements": [
        {{
            "target": "Variable being measured",
            "assay": "Technique/method",
            "readout": "What is quantified",
            "units": "Measurement units",
            "frequency": "When/how often to measure",
            "rationale": "Why this measurement"
        }}
    ],
    "coverage": {{
        "hypothesis_vars_covered": ["var1", "var2"],
        "missing_vars": [],
        "coverage_score": 0.95
    }}
}}
"""


class SuggestMeasurementsTool(BaseTool):
    """Suggest measurement variables and assays.

    Ensures all hypothesis variables are properly measured.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "suggest_measurements"

    @property
    def description(self) -> str:
        return (
            "Suggest measurement variables and assays for an experiment. "
            "Ensures all hypothesis variables (IV, DV, mediators) are properly "
            "measured with appropriate techniques. Returns coverage score."
        )

    @property
    def cost(self) -> float:
        return 0.3

    @property
    def category(self) -> str:
        return "design"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="experiment",
                type="dict",
                description="Experiment design",
                required=True,
            ),
            ToolParameter(
                name="hypothesis_vars",
                type="list",
                description="Variables from hypothesis to measure",
                required=False,
                default=[],
            ),
        ]

    async def run(
        self,
        experiment: dict,
        hypothesis_vars: list | None = None,
    ) -> dict[str, Any]:
        """Suggest measurements.

        Args:
            experiment: Experiment design
            hypothesis_vars: Variables to ensure are measured

        Returns:
            Dict with measurements and coverage
        """
        logger.info("Suggesting measurements...")

        try:
            from app.services.agent.study_plan.nodes.identify_measurements import (
                identify_measurements,
            )

            result = await identify_measurements(
                experiment=experiment,
                hypothesis_vars=hypothesis_vars or [],
            )
            return result

        except ImportError:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.1,
                )

            prompt = MEASUREMENTS_PROMPT.format(
                experiment=str(experiment),
                hypothesis_vars=str(hypothesis_vars or []),
            )
            response = await self._llm.ainvoke(prompt)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response.content)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            return {
                "measurements": [],
                "coverage": {
                    "hypothesis_vars_covered": [],
                    "missing_vars": hypothesis_vars or [],
                    "coverage_score": 0.0,
                },
            }
