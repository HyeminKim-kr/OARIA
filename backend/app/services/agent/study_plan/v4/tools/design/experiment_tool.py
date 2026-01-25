"""Design experiment tool."""

import logging
import uuid
from typing import Any

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import (
    BaseTool,
    ToolParameter,
    ensure_dict,
    ensure_list,
    safe_get,
)

logger = logging.getLogger(__name__)

DESIGN_EXPERIMENT_PROMPT = """Design an experiment to answer this research question.

Hypothesis:
{hypothesis}

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
                name="hypothesis",
                type="dict",
                description="Structured hypothesis (IV, DV, mechanism)",
                required=False,
                default={},
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
        question: dict | str | None = None,
        hypothesis: dict | str | None = None,
        evidence: list | str | None = None,
        constraints: list | str | None = None,
        feedback: list | str | None = None,
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
        # Handle missing parameter
        if question is None:
            logger.warning("design_experiment called without question parameter")
            return {
                "experiment": {},
                "error": "No question provided. Use decompose_questions to generate test questions first.",
            }
        # 타입 안전 변환
        q = ensure_dict(question)
        hyp = ensure_dict(hypothesis) if hypothesis else {}
        ev = ensure_list(evidence, [])
        cons = ensure_list(constraints, [])

        question_text = safe_get(q, "question", str(q)[:100] if isinstance(q, dict) else str(q)[:100])
        logger.info(f"Designing experiment for: {question_text}")

        try:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.2,
                )

            # Format evidence - 각 항목이 dict인지 확인
            evidence_lines = []
            for e in ev[:5]:
                if isinstance(e, dict):
                    evidence_lines.append(f"- {e.get('claim', str(e))[:200]}")
                else:
                    evidence_lines.append(f"- {str(e)[:200]}")
            evidence_text = "\n".join(evidence_lines) or "No specific evidence available"

            # Format constraints
            constraints_text = "\n".join([
                f"- {c}" if isinstance(c, str) else f"- {str(c)}"
                for c in cons
            ]) or "No specific constraints"

            # Format hypothesis
            if hyp:
                hypothesis_text = (
                    f"IV: {safe_get(hyp, 'iv', 'N/A')}\n"
                    f"DV: {safe_get(hyp, 'dv', 'N/A')}\n"
                    f"Mechanism: {safe_get(hyp, 'mechanism', 'N/A')}"
                )
            else:
                hypothesis_text = "Not specified"

            prompt = DESIGN_EXPERIMENT_PROMPT.format(
                hypothesis=hypothesis_text,
                question=str(q),
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
                    "objective": question_text,
                    "approach": "in_vitro",
                    "error": "Could not generate detailed design",
                }
            }
        except Exception as e:
            logger.error(f"Error designing experiment: {e}")
            return {
                "experiment": {
                    "id": f"EXP-{uuid.uuid4().hex[:8]}",
                    "name": "Experiment",
                    "error": str(e),
                }
            }
