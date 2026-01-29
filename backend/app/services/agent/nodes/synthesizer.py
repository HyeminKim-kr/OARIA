"""Evidence Synthesizer node (OAR-51)."""

import logging
import re
from collections.abc import AsyncGenerator

from app.schemas.chat import Reference
from app.services.llm_service import llm_service
from ..state import AgentState, TaskResult

logger = logging.getLogger(__name__)


def _extract_cited_indices(answer: str) -> set[int]:
    """
    답변에서 실제 인용된 reference 번호를 추출합니다.

    지원 형식:
    - [1], [2], [3]
    - [1, 2], [1, 3, 5]
    - [1,2,3] (공백 없음)

    Args:
        answer: LLM이 생성한 답변 텍스트

    Returns:
        인용된 reference 번호 set (1-indexed)
    """
    cited = set()

    # [숫자] 또는 [숫자, 숫자, ...] 패턴 매칭
    pattern = r'\[(\d+(?:\s*,\s*\d+)*)\]'
    matches = re.findall(pattern, answer)

    for match in matches:
        # 콤마로 분리하고 각 숫자 추출
        numbers = re.findall(r'\d+', match)
        for num in numbers:
            cited.add(int(num))

    return cited


def _filter_cited_references(
    answer: str,
    all_references: list[Reference]
) -> tuple[str, list[tuple[int, Reference]]]:
    """
    답변에서 실제 인용된 reference만 필터링합니다.

    스트리밍 호환성을 위해 답변의 인용 번호는 변경하지 않고,
    대신 각 reference에 원본 인용 번호를 함께 반환합니다.

    Args:
        answer: 원본 답변 (예: "결과는 [1]과 [5]에서...")
        all_references: 전체 reference 목록

    Returns:
        (원본 답변, [(원본 인용번호, reference), ...])
        예: ("결과는 [1]과 [5]에서...", [(1, ref1), (5, ref5)])
    """
    cited_indices = _extract_cited_indices(answer)

    if not cited_indices:
        logger.info("No citations found in answer, returning all references")
        # 모든 reference에 순차 번호 부여
        return answer, [(i + 1, ref) for i, ref in enumerate(all_references)]

    # 인용된 reference만 추출 (원본 번호 유지)
    cited_refs_with_index: list[tuple[int, Reference]] = []

    for idx in sorted(cited_indices):
        if 1 <= idx <= len(all_references):
            cited_refs_with_index.append((idx, all_references[idx - 1]))

    logger.info(
        f"Filtered references: {len(all_references)} → {len(cited_refs_with_index)} "
        f"(cited: {sorted(cited_indices)})"
    )

    return answer, cited_refs_with_index


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

    # Check for Gate 2 failures (OAR-12)
    gate2_failure = _check_gate2_failures(task_results)
    if gate2_failure:
        message, tips, suggestions = gate2_failure
        logger.warning(f"Gate 2 failed: {message}")
        formatted_response = _format_gate2_failure_response(message, tips, suggestions)
        return {
            "final_answer": formatted_response,
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

    # Filter to only cited references (with original citation indices)
    final_answer, cited_refs_with_index = _filter_cited_references(
        llm_response.content, all_references
    )

    # Extract just the references for citations (indices stored separately)
    cited_references = [ref for _, ref in cited_refs_with_index]
    citation_indices = [idx for idx, _ in cited_refs_with_index]

    logger.info(
        f"Synthesis complete. Answer length: {len(final_answer)}, "
        f"Citations: {len(cited_references)} (filtered from {len(all_references)}), "
        f"indices: {citation_indices}"
    )

    return {
        "final_answer": final_answer,
        "citations": cited_references,
        "citation_indices": citation_indices,  # 원본 인용 번호
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

    # Check for Gate 2 failures (OAR-12)
    gate2_failure = _check_gate2_failures(task_results)
    if gate2_failure:
        message, tips, suggestions = gate2_failure
        logger.warning(f"Gate 2 failed (stream): {message}")
        formatted_response = _format_gate2_failure_response(message, tips, suggestions)
        yield formatted_response
        return

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


def _check_gate2_failures(task_results: dict[str, TaskResult]) -> tuple[str, list[str] | None, list[str] | None] | None:
    """
    Check if any RAG task failed Gate 2 validation.

    Args:
        task_results: Results from all executed tasks

    Returns:
        Tuple of (error message, tips, suggestions) if Gate 2 failed, None otherwise
        - tips: Direction advice shown in message area
        - suggestions: Clickable question buttons
    """
    for task_id, result in task_results.items():
        # Check if this task has Gate 2 info and failed
        if result.gate2_passed is False:
            logger.info(f"Task {task_id} failed Gate 2: {result.gate2_reason}")
            # Return the content, tips, and suggestions
            return (result.content, result.gate2_tips, result.gate2_suggestions)

    return None


def _format_gate2_failure_response(
    message: str,
    tips: list[str] | None,
    suggestions: list[str] | None
) -> str:
    """
    Format Gate 2 failure response with tips and clickable questions.

    Args:
        message: Error message to display
        tips: Direction advice shown in message area
        suggestions: Clickable question buttons (rendered as buttons by frontend)

    Returns:
        Formatted response string with tips in message and suggestions block for buttons
    """
    response = message

    # Add tips to the message area
    if tips:
        response += "\n\n**💡 Tips for better results:**\n"
        for tip in tips:
            response += f"• {tip}\n"

    # Add clickable questions as hidden suggestions block (frontend parses and shows as buttons only)
    # Note: Frontend extracts these and removes the code block from display
    if suggestions:
        response += "\n```suggestions\n"
        for suggestion in suggestions:
            response += f"- {suggestion}\n"
        response += "```"

    return response
