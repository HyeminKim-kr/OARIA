"""Evidence Synthesizer node (OAR-51)."""

import logging
from collections.abc import AsyncGenerator

from app.schemas.chat import Reference
from app.services.llm_service import llm_service
from ..state import AgentState, TaskResult

logger = logging.getLogger(__name__)


async def synthesize_answer(state: AgentState) -> AgentState:
    """
    Synthesize final answer from all task results using llm_service (비동기).

    This node:
    1. Combines results from all executed tasks
    2. Generates a comprehensive answer with citations using llm_service prompt
    3. Deduplicates and collects all references

    Args:
        state: Current agent state with task_results

    Returns:
        Updated state with final_answer and citations
    """
    query = state["query"]
    task_results = state.get("task_results", {})
    subtasks = state.get("subtasks", [])

    if not task_results:
        logger.warning("No task results to synthesize")
        return {
            "final_answer": "검색 결과를 찾을 수 없습니다.",
            "citations": [],
        }

    logger.info(f"Synthesizing answer from {len(task_results)} task results...")

    # Collect all references and deduplicate
    all_references: list[Reference] = []
    seen_refs = set()

    for result in task_results.values():
        for ref in result.references:
            ref_key = (ref.paper_id, ref.chunk_id)
            if ref_key not in seen_refs:
                seen_refs.add(ref_key)
                all_references.append(ref)

    # Build context from task results (for llm_service)
    context = _build_context_from_results(task_results, subtasks, all_references)

    # Generate final answer using llm_service (uses the good prompt!) - 비동기
    llm_response = await llm_service.generate(
        question=query,
        context=context,
        references=all_references,
    )

    logger.info(
        f"Synthesis complete. Answer length: {len(llm_response.content)}, "
        f"Citations: {len(all_references)}"
    )

    return {
        "final_answer": llm_response.content,
        "citations": all_references,
    }


async def synthesize_answer_stream(state: AgentState) -> AsyncGenerator[str, None]:
    """
    Synthesize final answer with streaming tokens using llm_service (비동기).

    Yields tokens as they are generated.

    Note: 최종 state는 별도로 관리 필요 (AsyncGenerator는 return value 지원 안함)
    """
    query = state["query"]
    task_results = state.get("task_results", {})
    subtasks = state.get("subtasks", [])

    # Collect references
    all_references: list[Reference] = []
    seen_refs = set()

    for result in task_results.values():
        for ref in result.references:
            ref_key = (ref.paper_id, ref.chunk_id)
            if ref_key not in seen_refs:
                seen_refs.add(ref_key)
                all_references.append(ref)

    # Build context from task results (for llm_service)
    context = _build_context_from_results(task_results, subtasks, all_references)

    # Stream response using llm_service (uses the good prompt!) - 비동기
    async for chunk in llm_service.generate_stream(
        question=query,
        context=context,
        references=all_references,
    ):
        if chunk.token:
            yield chunk.token


def _build_context_from_results(
    task_results: dict[str, TaskResult],
    subtasks: list,
    references: list[Reference],
) -> str:
    """
    Build context string for llm_service from task results.

    This matches the format expected by llm_service's SYSTEM_PROMPT.
    """
    parts = []

    # Add each reference's content as context
    for i, ref in enumerate(references, 1):
        parts.append(
            f"[{i}] {ref.title}\n"
            f"저널: {ref.journal or 'N/A'}, 연도: {ref.year or 'N/A'}\n"
            f"섹션: {ref.section}\n"
            f"내용: {ref.snippet}"
        )

    return "\n\n---\n\n".join(parts)
