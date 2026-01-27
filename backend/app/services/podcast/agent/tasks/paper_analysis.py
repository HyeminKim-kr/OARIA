"""Task 2: Paper Analysis

Analyzes papers from Task 1 RAG results using LLM.
Does NOT call RAG - uses existing context from Task 1.
"""

import json
import logging
import time
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.chat import Reference
from ..state import PodcastTaskResult, PodcastTaskType
from ..prompts import PAPER_ANALYSIS_PROMPT, get_language_instruction
from .rag_search import format_references_for_podcast

logger = logging.getLogger(__name__)


async def execute_paper_analysis(
    goal: str,
    references: list[Reference],
    context: str,
    language: str = "ko",
) -> PodcastTaskResult:
    """
    Execute paper analysis using LLM (Task 2).

    Uses RAG results from Task 1 - does NOT call RAG again.
    Extracts key findings, trends, and clinical implications.

    Args:
        goal: User's podcast goal
        references: References from Task 1
        context: Context string from Task 1
        language: Output language (ko/en)

    Returns:
        PodcastTaskResult with analysis summary and key findings
    """
    start_time = time.perf_counter()

    result = PodcastTaskResult(
        task_type=PodcastTaskType.PAPER_ANALYSIS,
        status="running",
    )

    if not references:
        result.status = "completed"
        result.analysis_summary = "검색된 논문이 없어 분석을 수행할 수 없습니다."
        result.key_findings = []
        result.duration_ms = int((time.perf_counter() - start_time) * 1000)
        return result

    try:
        # Format context for LLM
        formatted_context = format_references_for_podcast(references)
        language_instruction = get_language_instruction(language)

        # Build prompt
        prompt = PAPER_ANALYSIS_PROMPT.format(
            goal=goal,
            context=formatted_context,
            language_instruction=language_instruction,
        )

        # Call LLM
        if not settings.openai_api_key:
            # Mock response for testing
            logger.warning("OpenAI API key not set, using mock analysis")
            analysis = _mock_analysis(goal, references, language)
        else:
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[
                    {"role": "system", "content": "You are a scientific paper analyst. Respond only in valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )

            analysis_text = response.choices[0].message.content or "{}"
            analysis = json.loads(analysis_text)

        # Extract results
        result.key_findings = analysis.get("key_findings", [])
        result.analysis_summary = analysis.get("summary", "")

        # Store full analysis in paper_recommendations for access by Task 3
        result.paper_recommendations = [{
            "trends": analysis.get("trends", ""),
            "controversies": analysis.get("controversies", ""),
            "clinical_implications": analysis.get("clinical_implications", ""),
            "knowledge_gaps": analysis.get("knowledge_gaps", ""),
        }]

        result.status = "completed"
        logger.info(f"Paper analysis completed: {len(result.key_findings)} key findings")

    except json.JSONDecodeError as e:
        logger.error(f"Paper analysis JSON parse error: {e}")
        result.status = "failed"
        result.error = f"Failed to parse analysis response: {e}"
    except Exception as e:
        logger.error(f"Paper analysis failed: {e}", exc_info=True)
        result.status = "failed"
        result.error = str(e)

    result.duration_ms = int((time.perf_counter() - start_time) * 1000)
    return result


def _mock_analysis(goal: str, references: list[Reference], language: str) -> dict[str, Any]:
    """Generate mock analysis for testing without OpenAI API."""
    if language == "ko":
        return {
            "key_findings": [
                {
                    "finding": f"{goal}에 관한 주요 발견 1",
                    "citation_indices": [1],
                    "significance": "임상적으로 중요한 의미가 있음"
                },
                {
                    "finding": f"{goal}에 관한 주요 발견 2",
                    "citation_indices": [1, 2],
                    "significance": "치료 방향에 영향을 미침"
                },
            ],
            "trends": "최근 연구들은 점점 더 정밀의료 접근법을 강조하고 있습니다.",
            "controversies": "일부 연구 간 치료 효능에 대한 의견 차이가 있습니다.",
            "clinical_implications": "임상 현장에서 환자 선별 기준이 중요해지고 있습니다.",
            "knowledge_gaps": "장기 추적 연구가 더 필요합니다.",
            "summary": f"이 논문들은 {goal}에 대한 최신 연구 동향을 보여줍니다.",
        }
    else:
        return {
            "key_findings": [
                {
                    "finding": f"Key finding 1 about {goal}",
                    "citation_indices": [1],
                    "significance": "Clinically significant"
                },
                {
                    "finding": f"Key finding 2 about {goal}",
                    "citation_indices": [1, 2],
                    "significance": "Impacts treatment direction"
                },
            ],
            "trends": "Recent studies emphasize precision medicine approaches.",
            "controversies": "Some disagreement exists on treatment efficacy.",
            "clinical_implications": "Patient selection criteria are becoming more important.",
            "knowledge_gaps": "Long-term follow-up studies are needed.",
            "summary": f"These papers show the latest research trends on {goal}.",
        }


def format_analysis_for_script(task_result: PodcastTaskResult) -> str:
    """
    Format the analysis results for Task 3 script generation.

    Args:
        task_result: Completed Task 2 result

    Returns:
        Formatted analysis summary string
    """
    parts = []

    # Summary
    if task_result.analysis_summary:
        parts.append(f"## Executive Summary\n{task_result.analysis_summary}\n")

    # Key findings
    if task_result.key_findings:
        parts.append("## Key Findings")
        for i, finding in enumerate(task_result.key_findings, 1):
            if isinstance(finding, dict):
                parts.append(f"{i}. {finding.get('finding', '')}")
                if finding.get("citation_indices"):
                    parts.append(f"   Sources: {finding['citation_indices']}")
                if finding.get("significance"):
                    parts.append(f"   Significance: {finding['significance']}")
            else:
                parts.append(f"{i}. {finding}")
        parts.append("")

    # Additional context
    if task_result.paper_recommendations:
        extra = task_result.paper_recommendations[0]
        if extra.get("trends"):
            parts.append(f"## Trends\n{extra['trends']}\n")
        if extra.get("clinical_implications"):
            parts.append(f"## Clinical Implications\n{extra['clinical_implications']}\n")

    return "\n".join(parts)
