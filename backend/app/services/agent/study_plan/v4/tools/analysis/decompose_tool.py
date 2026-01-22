"""Decompose questions tool - NSPE framework."""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)

DECOMPOSE_PROMPT = """You are a scientific research planner.
Decompose the hypothesis into testable questions using the NSPE framework.

Structured Hypothesis:
{hypothesis}

NSPE Framework:
- N (Necessity): Is the IV necessary for the DV? (If we remove IV, does DV still occur?)
- S (Sufficiency): Is the IV sufficient for the DV? (If only IV present, does DV occur?)
- P (Pathway): What is the mechanism connecting IV to DV?
- E (Epistasis): Are there interactions with other factors?

Generate 4-6 specific, testable questions that address these aspects.

Respond in JSON format:
{{
    "questions": [
        {{
            "id": "Q1",
            "category": "necessity",
            "question": "Is [IV] required for [DV]?",
            "experimental_approach": "Knockdown/knockout of IV",
            "expected_outcome": "DV should be reduced/eliminated",
            "priority": "high"
        }},
        ...
    ]
}}
"""


class DecomposeQuestionsTool(BaseTool):
    """Decompose hypothesis into testable questions.

    Uses the NSPE framework:
    - Necessity
    - Sufficiency
    - Pathway interaction
    - Epistasis
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "decompose_questions"

    @property
    def description(self) -> str:
        return (
            "Decompose a structured hypothesis into testable research questions "
            "using the NSPE framework (Necessity, Sufficiency, Pathway, Epistasis). "
            "Each question maps to a specific experimental approach. "
            "Requires a parsed hypothesis as input."
        )

    @property
    def cost(self) -> float:
        return 0.2

    @property
    def category(self) -> str:
        return "analysis"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="structured_hypothesis",
                type="dict",
                description="Parsed hypothesis from parse_hypothesis tool",
                required=True,
            ),
        ]

    async def run(self, structured_hypothesis: dict) -> dict[str, Any]:
        """Generate test questions from structured hypothesis.

        Args:
            structured_hypothesis: Parsed hypothesis with IV, DV, etc.

        Returns:
            Dict with list of testable questions
        """
        logger.info("Decomposing hypothesis into questions...")

        try:
            from app.services.agent.study_plan.nodes.decompose_questions import (
                decompose_to_questions,
            )

            result = await decompose_to_questions(structured_hypothesis)
            return {"questions": result}

        except ImportError:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.2,
                )

            prompt = DECOMPOSE_PROMPT.format(
                hypothesis=str(structured_hypothesis)
            )
            response = await self._llm.ainvoke(prompt)

            import json
            import re

            json_match = re.search(r"\{[^{}]*\"questions\"[^{}]*\}", response.content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            # Fallback questions
            return {
                "questions": [
                    {
                        "id": "Q1",
                        "category": "necessity",
                        "question": f"Is {structured_hypothesis.get('iv', 'IV')} necessary for {structured_hypothesis.get('dv', 'DV')}?",
                        "priority": "high",
                    },
                    {
                        "id": "Q2",
                        "category": "sufficiency",
                        "question": f"Is {structured_hypothesis.get('iv', 'IV')} sufficient for {structured_hypothesis.get('dv', 'DV')}?",
                        "priority": "high",
                    },
                    {
                        "id": "Q3",
                        "category": "pathway",
                        "question": f"What is the mechanism linking {structured_hypothesis.get('iv', 'IV')} to {structured_hypothesis.get('dv', 'DV')}?",
                        "priority": "medium",
                    },
                ]
            }
