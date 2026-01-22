"""Synthesize plan tool."""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter

logger = logging.getLogger(__name__)

SYNTHESIZE_PROMPT = """Create a comprehensive research plan from these components.

Hypothesis:
{hypothesis}

Experiments:
{experiments}

Evidence:
{evidence}

Write a complete research plan including:
1. Executive Summary
2. Background and Rationale
3. Specific Aims
4. Experimental Strategy
5. Expected Outcomes
6. Timeline
7. References

Use clear scientific language. Be specific about methods and expected results.

Format the plan in Markdown.
"""


class SynthesizePlanTool(BaseTool):
    """Synthesize final research plan.

    Combines all components into a coherent plan document.
    """

    def __init__(self, llm: ChatOpenAI | None = None):
        self._llm = llm

    @property
    def name(self) -> str:
        return "synthesize_plan"

    @property
    def description(self) -> str:
        return (
            "Synthesize all components into a final research plan document. "
            "Creates a comprehensive plan with executive summary, aims, "
            "experimental strategy, and timeline. Use after all experiments "
            "are designed and validated."
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
                name="experiments",
                type="list",
                description="List of experiment designs",
                required=True,
            ),
            ToolParameter(
                name="evidence",
                type="list",
                description="Supporting evidence snippets",
                required=False,
                default=[],
            ),
            ToolParameter(
                name="metadata",
                type="dict",
                description="Additional metadata (hypothesis, constraints, etc.)",
                required=False,
                default={},
            ),
        ]

    async def run(
        self,
        experiments: list[dict],
        evidence: list | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Synthesize the plan.

        Args:
            experiments: Experiment designs
            evidence: Supporting evidence
            metadata: Additional metadata

        Returns:
            Dict with plan and summary
        """
        logger.info(f"Synthesizing plan from {len(experiments)} experiments...")

        try:
            from app.services.agent.study_plan.nodes.synthesize_plan import (
                synthesize_plan,
            )

            result = await synthesize_plan(
                experiments=experiments,
                evidence=evidence or [],
                metadata=metadata or {},
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

            # Format components
            hypothesis = metadata.get("hypothesis", {}) if metadata else {}
            exp_text = "\n".join([
                f"- {e.get('name', 'Experiment')}: {e.get('objective', '')}"
                for e in experiments
            ])
            evidence_text = "\n".join([
                f"- {e.get('claim', str(e))[:100]}"
                for e in (evidence or [])[:5]
            ])

            prompt = SYNTHESIZE_PROMPT.format(
                hypothesis=str(hypothesis),
                experiments=exp_text,
                evidence=evidence_text,
            )
            response = await self._llm.ainvoke(prompt)

            plan = response.content

            # Generate summary
            summary = self._generate_summary(experiments, hypothesis)

            return {
                "plan": plan,
                "summary": summary,
            }

    def _generate_summary(
        self,
        experiments: list[dict],
        hypothesis: dict,
    ) -> str:
        """Generate executive summary."""
        lines = [
            "## Executive Summary",
            "",
            f"This study plan tests the hypothesis that "
            f"{hypothesis.get('iv', 'the independent variable')} "
            f"affects {hypothesis.get('dv', 'the dependent variable')}.",
            "",
            f"**Number of Experiments:** {len(experiments)}",
            "",
            "**Experimental Approaches:**",
        ]

        approaches = set()
        for exp in experiments:
            if approach := exp.get("approach"):
                approaches.add(approach)

        for approach in approaches:
            lines.append(f"- {approach.replace('_', ' ').title()}")

        return "\n".join(lines)
