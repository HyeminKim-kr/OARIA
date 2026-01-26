"""Analyze methodology tool."""

import logging
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

METHODOLOGY_PROMPT = """Analyze the experimental methodologies used in these papers.

Papers:
{papers}

Extract:
1. Common experimental approaches
2. Cell lines / animal models used
3. Assays and techniques
4. Sample sizes and statistical methods
5. Key protocols

Respond in JSON:
{{
    "common_approaches": ["approach1", "approach2"],
    "cell_lines": ["cell line 1", "cell line 2"],
    "animal_models": ["model 1"],
    "assays": [
        {{
            "name": "assay name",
            "purpose": "what it measures",
            "frequency": "how often used"
        }}
    ],
    "statistical_methods": ["method1", "method2"],
    "recommended_approach": "brief recommendation based on patterns"
}}
"""


class AnalyzeMethodologyTool(BaseTool):
    """Analyze methodologies from retrieved papers.

    Extracts common experimental approaches, assays,
    and statistical methods from the literature.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "analyze_methodology"

    @property
    def description(self) -> str:
        return (
            "Analyze experimental methodologies from retrieved papers. "
            "Extracts common approaches, assays, cell lines, animal models, "
            "and statistical methods. Use after searching for papers to "
            "understand what methods are commonly used in the field."
        )

    @property
    def cost(self) -> float:
        return 0.4

    @property
    def category(self) -> str:
        return "analysis"

    def _get_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="papers",
                type="list",
                description="List of papers to analyze",
                required=True,
            ),
        ]

    async def run(self, papers: list[dict]) -> dict[str, Any]:
        """Analyze methodologies from papers.

        Args:
            papers: List of paper dicts with abstracts/content

        Returns:
            Dict with methodology patterns
        """
        logger.info(f"Analyzing methodology from {len(papers)} papers...")

        if not papers:
            return {
                "common_approaches": [],
                "assays": [],
                "cell_lines": [],
                "animal_models": [],
                "error": "No papers provided",
            }

        try:
            from app.services.agent.study_plan.nodes.analyze_methodology import (
                analyze_methodology,
            )

            result = await analyze_methodology(papers)
            return result

        except ImportError:
            if self._llm is None:
                from app.config import get_settings

                settings = get_settings()
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=0.1,
                )

            # Summarize papers for prompt
            paper_summaries = []
            papers_list = ensure_list(papers, [])
            for p in papers_list[:10]:  # Limit to avoid token overflow
                p_dict = ensure_dict(p) if not isinstance(p, dict) else p
                title = safe_get(p_dict, "title", "Unknown")
                abstract = safe_get(p_dict, "abstract", "")
                if isinstance(abstract, str):
                    abstract = abstract[:500]
                paper_summaries.append(f"Title: {title}\nAbstract: {abstract}")

            prompt = METHODOLOGY_PROMPT.format(
                papers="\n\n---\n\n".join(paper_summaries)
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
                "common_approaches": [],
                "assays": [],
                "cell_lines": [],
                "animal_models": [],
                "error": "Could not parse methodology",
            }
