"""Critique design tool."""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)

CRITIQUE_PROMPT = """Critically evaluate this experimental design.

Design:
{design}

Evaluate on these criteria:
1. Scientific Rigor: Are controls adequate? Is methodology sound?
2. Completeness: Are all hypothesis variables tested?
3. Feasibility: Can this be realistically executed?
4. Statistical Power: Are sample sizes adequate?
5. Reproducibility: Is the design replicable?

Provide a quality score (0.0 to 1.0) and specific issues/suggestions.

Respond in JSON:
{{
    "score": 0.85,
    "criteria_scores": {{
        "scientific_rigor": 0.9,
        "completeness": 0.85,
        "feasibility": 0.8,
        "statistical_power": 0.85,
        "reproducibility": 0.9
    }},
    "issues": [
        {{
            "type": "control_gap",
            "severity": "high",
            "description": "Missing rescue experiment",
            "affected_experiment": "EXP-001"
        }}
    ],
    "suggestions": [
        "Add rescue experiment to confirm specificity",
        "Increase sample size for in vivo study"
    ],
    "summary": "Brief overall assessment"
}}
"""


class CritiqueDesignTool(BaseTool):
    """Critique overall design quality.

    Evaluates the complete experimental design for
    scientific rigor, completeness, and feasibility.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "critique_design"

    @property
    def description(self) -> str:
        return (
            "Critically evaluate the overall experimental design. "
            "Assesses scientific rigor, completeness, feasibility, "
            "statistical power, and reproducibility. Returns quality "
            "score and specific improvement suggestions."
        )

    @property
    def cost(self) -> float:
        return 0.5

    @property
    def category(self) -> str:
        return "validation"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="design",
                type="dict",
                description="Complete design with experiments, controls, measurements",
                required=True,
            ),
        ]

    async def run(self, design: dict) -> dict[str, Any]:
        """Critique the design.

        Args:
            design: Complete experimental design

        Returns:
            Critique results with score and suggestions
        """
        logger.info("Critiquing design...")

        try:
            from app.services.agent.study_plan.nodes.critique_refine import (
                critique_design,
            )

            result = await critique_design(design)
            return result

        except ImportError:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.1,
                )

            prompt = CRITIQUE_PROMPT.format(design=str(design))
            response = await self._llm.ainvoke(prompt)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response.content)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # Fallback evaluation
            experiments = design.get("experiments", [])
            controls = design.get("controls", {})
            measurements = design.get("measurements", [])

            base_score = 0.5
            if experiments:
                base_score += 0.1
            if controls:
                base_score += 0.1
            if measurements:
                base_score += 0.1

            return {
                "score": base_score,
                "criteria_scores": {
                    "scientific_rigor": base_score,
                    "completeness": base_score,
                    "feasibility": 0.7,
                    "statistical_power": 0.6,
                    "reproducibility": 0.7,
                },
                "issues": [],
                "suggestions": [],
                "summary": "Basic evaluation completed",
            }
