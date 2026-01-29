"""Task 1: RAG Search

The ONLY RAG call in the podcast agent pipeline.
Searches for relevant papers based on the user's goal.
"""

import logging
import time
from typing import Any

from app.services.rag_service import rag_service
from app.services.gates.gate2_retrieval import Gate2Service
from app.schemas.chat import Reference
from ..state import PodcastTaskResult, PodcastTaskType

logger = logging.getLogger(__name__)


async def execute_rag_search(
    goal: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 10,
) -> PodcastTaskResult:
    """
    Execute RAG search for podcast content (Task 1).

    This is the ONLY RAG call in the entire podcast generation pipeline.
    All subsequent tasks reuse the results from this search.

    Args:
        goal: User's podcast goal (e.g., "EGFR 표적 치료의 최신 동향")
        filters: Optional search filters (year_from, year_to, etc.)
        top_k: Number of results to return (default 10 for podcast)

    Returns:
        PodcastTaskResult with references and context
    """
    start_time = time.perf_counter()

    result = PodcastTaskResult(
        task_type=PodcastTaskType.RAG_SEARCH,
        status="running",
    )

    try:
        # Parse filters
        year_from = None
        year_to = None
        sections = None

        if filters:
            year_from = filters.get("year_from")
            year_to = filters.get("year_to")
            sections = filters.get("sections")

        logger.info(f"Podcast RAG Search: goal='{goal[:50]}...', filters={filters}")

        # Execute RAG search with higher top_k for podcast
        # Podcast needs more context than Q&A
        rag_result = await rag_service.retrieve(
            query=goal,
            year_from=year_from,
            year_to=year_to,
            sections=sections,
            use_reranker=True,
        )

        # Gate 2 validation
        gate2_service = Gate2Service()
        gate2_result = gate2_service.validate(rag_result.references)

        result.references = rag_result.references
        result.context = rag_result.context
        result.gate2_passed = gate2_result.passed
        result.gate2_reason = gate2_result.reason.value if gate2_result.reason else None

        if not gate2_result.passed:
            # Gate 2 failed, but we still return partial results
            logger.warning(
                f"Podcast RAG Gate 2 failed: {gate2_result.message}",
                extra={
                    "reason": gate2_result.reason,
                    "max_similarity": gate2_result.max_similarity,
                    "relevant_count": gate2_result.relevant_count,
                },
            )
            result.status = "completed"  # Still mark as completed, let service decide
        else:
            result.status = "completed"
            logger.info(
                f"Podcast RAG Search completed: {len(rag_result.references)} references found"
            )

    except Exception as e:
        logger.error(f"Podcast RAG Search failed: {e}", exc_info=True)
        result.status = "failed"
        result.error = str(e)

    result.duration_ms = int((time.perf_counter() - start_time) * 1000)
    return result


def format_references_for_podcast(references: list[Reference]) -> str:
    """
    Format references into a numbered context string for LLM prompts.

    Returns:
        Formatted context with [1], [2], etc. markers
    """
    if not references:
        return "No relevant papers found."

    context_parts = []
    for idx, ref in enumerate(references, 1):
        context_parts.append(
            f"[{idx}] {ref.title}\n"
            f"    Journal: {ref.journal or 'N/A'}, Year: {ref.year or 'N/A'}\n"
            f"    Section: {ref.section}\n"
            f"    Content: {ref.snippet}\n"
        )

    return "\n".join(context_parts)


def get_paper_summary_list(references: list[Reference]) -> list[dict[str, Any]]:
    """
    Get a list of paper summaries for Task 2 analysis.

    Returns:
        List of dicts with paper_id, title, journal, year
    """
    seen_papers: set[str] = set()
    papers = []

    for ref in references:
        if ref.paper_id not in seen_papers:
            seen_papers.add(ref.paper_id)
            papers.append({
                "paper_id": ref.paper_id,
                "title": ref.title,
                "journal": ref.journal,
                "year": ref.year,
            })

    return papers
