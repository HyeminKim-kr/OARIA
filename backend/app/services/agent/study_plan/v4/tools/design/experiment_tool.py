"""Design experiment tool."""

import logging
import uuid
from typing import Any

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)

DESIGN_EXPERIMENT_PROMPT = """Design an experiment to answer this research question.

Question: {question}

Available Evidence:
{evidence}

Constraints:
{constraints}

Design a rigorous experiment including:
1. Objective
2. Experimental approach
3. Model system (cell line, animal model, etc.)
4. Key methods and techniques
5. Sample groups
6. Primary endpoints
7. Statistical plan

Respond in JSON:
{{
    "id": "EXP-001",
    "name": "Experiment name",
    "objective": "What this experiment will determine",
    "approach": "in_vitro | in_vivo | clinical | computational",
    "model_system": {{
        "type": "cell_line | animal | human",
        "name": "Specific model name",
        "rationale": "Why this model is appropriate"
    }},
    "groups": [
        {{
            "name": "Group name",
            "treatment": "What is applied",
            "n": 10,
            "purpose": "Why this group is needed"
        }}
    ],
    "methods": ["method1", "method2"],
    "endpoints": {{
        "primary": "Main outcome measure",
        "secondary": ["Secondary measure 1"]
    }},
    "timeline": "Estimated duration",
    "statistical_plan": "Analysis approach"
}}
"""


class DesignExperimentTool(BaseTool):
    """Design an individual experiment.

    Creates a detailed experimental design to answer
    a specific research question.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "design_experiment"

    @property
    def description(self) -> str:
        return (
            "Design a detailed experiment to answer a specific research question. "
            "Takes a question from the NSPE decomposition and relevant evidence "
            "to create an experimental design with model system, groups, methods, "
            "and statistical plan."
        )

    @property
    def cost(self) -> float:
        return 0.5

    @property
    def category(self) -> str:
        return "design"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="question",
                type="dict",
                description="Research question to answer",
                required=True,
            ),
            ToolParameter(
                name="evidence",
                type="list",
                description="Relevant evidence snippets",
                required=False,
                default=[],
            ),
            ToolParameter(
                name="constraints",
                type="list",
                description="Constraints on the design",
                required=False,
                default=[],
            ),
            ToolParameter(
                name="feedback",
                type="list",
                description="Feedback from previous critique",
                required=False,
                default=[],
            ),
        ]

    async def run(
        self,
        question: dict,
        evidence: list | None = None,
        constraints: list | None = None,
        feedback: list | None = None,
    ) -> dict[str, Any]:
        """Design an experiment.

        Args:
            question: Research question to answer
            evidence: Relevant evidence
            constraints: Design constraints
            feedback: Previous critique feedback

        Returns:
            Experiment design dict
        """
        logger.info(f"Designing experiment for: {question.get('question', str(question)[:100])}")

        try:
            from app.services.agent.study_plan.nodes.design_experiments import (
                design_single_experiment,
            )

            result = await design_single_experiment(
                question=question,
                evidence=evidence or [],
                constraints=constraints or [],
            )
            return {"experiment": result}

        except ImportError:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.2,
                )

            # Format evidence
            evidence_text = "\n".join([
                f"- {e.get('claim', str(e))[:200]}"
                for e in (evidence or [])[:5]
            ]) or "No specific evidence available"

            # Format constraints
            constraints_text = "\n".join([
                f"- {c}" for c in (constraints or [])
            ]) or "No specific constraints"

            prompt = DESIGN_EXPERIMENT_PROMPT.format(
                question=str(question),
                evidence=evidence_text,
                constraints=constraints_text,
            )
            response = await self._llm.ainvoke(prompt)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response.content)
            if json_match:
                try:
                    experiment = json.loads(json_match.group())
                    experiment["id"] = f"EXP-{uuid.uuid4().hex[:8]}"
                    return {"experiment": experiment}
                except json.JSONDecodeError:
                    pass

            return {
                "experiment": {
                    "id": f"EXP-{uuid.uuid4().hex[:8]}",
                    "name": "Experiment",
                    "objective": question.get("question", "Test hypothesis"),
                    "approach": "in_vitro",
                    "error": "Could not generate detailed design",
                }
            }
