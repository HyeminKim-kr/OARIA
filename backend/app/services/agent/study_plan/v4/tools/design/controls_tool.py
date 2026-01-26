"""Design controls tool."""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import (
    BaseTool,
    ToolParameter,
    ensure_dict,
    safe_get,
)

logger = logging.getLogger(__name__)

DESIGN_CONTROLS_PROMPT = """Design appropriate controls for this experiment.

Experiment:
{experiment}

Every rigorous experiment needs:
1. Vehicle/Negative Control: Shows baseline without treatment
2. Positive Control: Validates the assay works
3. Technical Controls: Address potential confounds

For each control, specify:
- Type (vehicle, positive, technical)
- Name
- Purpose
- What it controls for
- Expected outcome

Respond in JSON:
{{
    "controls": [
        {{
            "type": "vehicle",
            "name": "DMSO control",
            "purpose": "Baseline without active compound",
            "controls_for": "Drug vehicle effects",
            "expected_outcome": "No significant change"
        }},
        {{
            "type": "positive",
            "name": "Known inhibitor",
            "purpose": "Validate assay sensitivity",
            "controls_for": "Assay function",
            "expected_outcome": "Expected positive result"
        }},
        ...
    ],
    "validation": {{
        "has_vehicle": true,
        "has_positive": true,
        "has_technical": true,
        "completeness_score": 0.95
    }}
}}
"""


class DesignControlsTool(BaseTool):
    """Design experimental controls.

    Creates proper controls for experiments including
    vehicle, positive, and technical controls.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "design_controls"

    @property
    def description(self) -> str:
        return (
            "Design experimental controls for a given experiment. "
            "Creates vehicle/negative controls, positive controls, "
            "and technical controls. Essential for validating experimental results."
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
                description="Experiment design to add controls to",
                required=True,
            ),
        ]

    async def run(self, experiment: dict | str | None = None) -> dict[str, Any]:
        """Design controls for experiment.

        Args:
            experiment: Experiment design dict

        Returns:
            Dict with controls list
        """
        # Handle missing parameter
        if experiment is None:
            logger.warning("design_controls called without experiment parameter")
            return {
                "controls": [],
                "error": "No experiment provided. Call design_experiment first.",
            }

        # 타입 안전 변환
        exp = ensure_dict(experiment)
        exp_name = safe_get(exp, "name", "experiment")
        logger.info(f"Designing controls for: {exp_name}")

        try:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.1,
                )

            prompt = DESIGN_CONTROLS_PROMPT.format(
                experiment=str(exp)
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

            # Fallback basic controls
            return {
                "controls": [
                    {
                        "type": "vehicle",
                        "name": "Vehicle control",
                        "purpose": "Baseline without treatment",
                        "controls_for": "Treatment vehicle effects",
                        "expected_outcome": "No significant change",
                    },
                    {
                        "type": "positive",
                        "name": "Positive control",
                        "purpose": "Validate assay function",
                        "controls_for": "Assay sensitivity",
                        "expected_outcome": "Expected positive result",
                    },
                ],
                "validation": {
                    "has_vehicle": True,
                    "has_positive": True,
                    "has_technical": False,
                    "completeness_score": 0.7,
                },
            }
        except Exception as e:
            logger.error(f"Error designing controls: {e}")
            return {
                "controls": [],
                "validation": {
                    "has_vehicle": False,
                    "has_positive": False,
                    "has_technical": False,
                    "completeness_score": 0.0,
                },
                "error": str(e),
            }
