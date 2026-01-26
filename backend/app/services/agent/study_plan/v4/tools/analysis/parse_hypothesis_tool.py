"""Parse hypothesis tool."""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)

PARSE_HYPOTHESIS_PROMPT = """You are a scientific hypothesis analyzer.
Parse the given hypothesis and extract its key components.

Hypothesis: {hypothesis}

Extract the following:
1. Independent Variable (IV): The cause or manipulated variable
2. Dependent Variable (DV): The effect or measured outcome
3. Mediators: Variables that explain HOW the IV affects the DV
4. Moderators: Variables that affect WHEN or for WHOM the effect occurs
5. Confidence: How clearly structured is this hypothesis (0.0 to 1.0)

Respond in JSON format:
{{
    "iv": "independent variable",
    "dv": "dependent variable",
    "mediators": ["mediator1", "mediator2"],
    "moderators": ["moderator1"],
    "mechanism": "brief description of proposed mechanism",
    "context": "research context or domain",
    "confidence": 0.85
}}
"""


class ParseHypothesisTool(BaseTool):
    """Parse and structure a research hypothesis.

    Extracts key variables and relationships from
    natural language hypothesis statements.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "parse_hypothesis"

    @property
    def description(self) -> str:
        return (
            "Parse a research hypothesis to extract its key components: "
            "independent variable (IV), dependent variable (DV), mediators, "
            "and moderators. This is typically the first step in study planning. "
            "Returns a structured representation of the hypothesis."
        )

    @property
    def cost(self) -> float:
        return 0.2  # Low cost

    @property
    def category(self) -> str:
        return "analysis"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="hypothesis",
                type="str",
                description="The research hypothesis to parse",
                required=True,
            ),
        ]

    async def run(self, hypothesis: str) -> dict[str, Any]:
        """Parse hypothesis into structured form.

        Args:
            hypothesis: Natural language hypothesis

        Returns:
            Structured hypothesis with IV, DV, mediators, etc.
        """
        logger.info(f"Parsing hypothesis: {hypothesis[:100]}...")

        try:
            # Try to use existing node implementation
            from app.services.agent.study_plan.nodes.parse_hypothesis import (
                parse_hypothesis,
            )

            # 노드 함수는 state dict를 기대하므로 변환
            state_dict = {"user_input": hypothesis}
            result = await parse_hypothesis(state_dict)

            # 결과를 v4 에이전트가 기대하는 형식으로 변환
            hyp = result.get("hypothesis")
            if hyp:
                return {
                    "iv": getattr(hyp, "independent_variable", "unknown"),
                    "dv": getattr(hyp, "dependent_variable", "unknown"),
                    "mediators": getattr(hyp, "mediating_variables", []),
                    "moderators": getattr(hyp, "moderating_variables", []),
                    "mechanism": getattr(hyp, "mechanism_pathway", ""),
                    "keywords": getattr(hyp, "keywords", []),
                    "expanded_keywords": getattr(hyp, "expanded_keywords", []),
                    "confidence": result.get("hypothesis_confidence", 0.5),
                }
            return result

        except ImportError:
            # Fallback to LLM-based parsing
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.1,
                )

            prompt = PARSE_HYPOTHESIS_PROMPT.format(hypothesis=hypothesis)
            response = await self._llm.ainvoke(prompt)

            # Parse JSON from response
            import json
            import re

            json_match = re.search(r"\{[^{}]*\}", response.content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            # Fallback structure
            return {
                "iv": "unknown",
                "dv": "unknown",
                "mediators": [],
                "moderators": [],
                "mechanism": hypothesis[:200],
                "confidence": 0.5,
            }
