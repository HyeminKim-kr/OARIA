"""Executor node (OAR-50)."""

import asyncio
import logging
import time
from collections import defaultdict

from openai import AsyncOpenAI

from app.config import settings
from app.services.rag_service import rag_service
from app.services.gates import gate2_service, Gate2Result
from app.schemas.chat import Reference
from ..state import AgentState, SubTask, TaskResult, ToolType
from ..prompts import COMPARE_SYSTEM, COMPARE_USER

logger = logging.getLogger(__name__)


async def execute_tasks(state: AgentState) -> AgentState:
    """
    Execute all sub-tasks according to the execution plan.

    This node:
    1. Executes tasks in dependency order
    2. Runs independent tasks in parallel
    3. Collects results and citations

    Args:
        state: Current agent state with subtasks and execution_plan

    Returns:
        Updated state with task_results
    """
    subtasks = state.get("subtasks", [])
    execution_plan = state.get("execution_plan", [])

    if not subtasks:
        logger.warning("No subtasks to execute")
        return {"task_results": {}}

    logger.info(f"Executing {len(subtasks)} tasks...")

    task_map = {task.id: task for task in subtasks}
    task_results: dict[str, TaskResult] = {}

    # Group tasks by dependencies for parallel execution
    in_degree = {task.id: len(task.depends_on) for task in subtasks}
    dependents = defaultdict(list)

    for task in subtasks:
        for dep_id in task.depends_on:
            dependents[dep_id].append(task.id)

    ready = [task_id for task_id in execution_plan if in_degree[task_id] == 0]

    while ready:
        # Execute ready tasks in parallel with asyncio.gather
        async def execute_task(task_id: str) -> tuple[str, TaskResult]:
            task = task_map[task_id]
            logger.info(f"Executing task {task_id}: {task.query[:50]}...")
            try:
                result = await _execute_single_task(task, task_results)
                logger.info(
                    f"Task {task_id} completed in {result.duration_ms}ms "
                    f"with {len(result.references)} references"
                )
                return task_id, result
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                return task_id, TaskResult(
                    task_id=task_id,
                    content="",
                    references=[],
                    error=str(e),
                )

        # 병렬 실행
        results = await asyncio.gather(*[execute_task(tid) for tid in ready])
        for task_id, result in results:
            task_results[task_id] = result

        # Find next batch of ready tasks
        next_ready = []
        for task_id in ready:
            for dependent_id in dependents[task_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    next_ready.append(dependent_id)

        ready = next_ready

    return {"task_results": task_results}


async def _execute_single_task(
    task: SubTask, previous_results: dict[str, TaskResult]
) -> TaskResult:
    """Execute a single task based on its tool type."""
    start_time = time.perf_counter()

    if task.tool == ToolType.RAG_SEARCH:
        result = await _execute_rag_search(task)
    elif task.tool == ToolType.COMPARE:
        result = await _execute_compare(task, previous_results)
    elif task.tool == ToolType.SUMMARIZE:
        result = _execute_summarize(task, previous_results)
    else:
        # Fallback to RAG search
        result = await _execute_rag_search(task)

    result.duration_ms = int((time.perf_counter() - start_time) * 1000)
    return result


async def _execute_rag_search(task: SubTask) -> TaskResult:
    """Execute RAG search using existing rag_service (비동기)."""
    retrieval_result = await rag_service.retrieve(task.query)

    # Gate 2: Retrieval Confidence 검증 (OAR-12)
    gate2_result = gate2_service.validate(retrieval_result.references)

    if not gate2_result.passed:
        logger.warning(
            f"Gate 2 failed for task {task.id}: {gate2_result.reason} - {gate2_result.message}"
        )
        return TaskResult(
            task_id=task.id,
            content=gate2_result.message or "검색 결과 품질이 기준에 미달합니다.",
            references=retrieval_result.references,  # 참조는 전달 (경고와 함께)
            gate2_passed=False,
            gate2_reason=gate2_result.reason.value if gate2_result.reason else None,
        )

    return TaskResult(
        task_id=task.id,
        content=retrieval_result.context,
        references=retrieval_result.references,
        gate2_passed=True,
    )


async def _execute_compare(
    task: SubTask, previous_results: dict[str, TaskResult]
) -> TaskResult:
    """Execute comparison using LLM with context from previous tasks (비동기)."""
    # Gather context from dependent tasks
    context_parts = []
    all_references = []

    for dep_id in task.depends_on:
        if dep_id in previous_results:
            dep_result = previous_results[dep_id]
            context_parts.append(f"[{dep_id}]: {dep_result.content}")
            all_references.extend(dep_result.references)

    context = "\n\n".join(context_parts)

    # Use LLM for comparison (비동기)
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": COMPARE_SYSTEM},
            {
                "role": "user",
                "content": COMPARE_USER.format(query=task.query, context=context),
            },
        ],
        temperature=0.3,
    )

    comparison_content = response.choices[0].message.content

    return TaskResult(
        task_id=task.id,
        content=comparison_content,
        references=all_references,  # Pass through references from source tasks
    )


def _execute_summarize(
    task: SubTask, previous_results: dict[str, TaskResult]
) -> TaskResult:
    """Summarize results from dependent tasks."""
    # Gather content from dependent tasks
    content_parts = []
    all_references = []

    for dep_id in task.depends_on:
        if dep_id in previous_results:
            dep_result = previous_results[dep_id]
            content_parts.append(dep_result.content)
            all_references.extend(dep_result.references)

    combined_content = "\n\n---\n\n".join(content_parts)

    return TaskResult(
        task_id=task.id,
        content=combined_content,
        references=all_references,
    )


async def execute_direct_rag(state: AgentState) -> AgentState:
    """
    Execute direct RAG for simple queries (bypasses decomposition).

    Used when complexity is SIMPLE - goes directly from
    analyze_complexity to synthesis.
    """
    query = state["query"]
    logger.info(f"Executing direct RAG for simple query: {query[:50]}...")

    start_time = time.perf_counter()

    # Use existing RAG service (비동기)
    retrieval_result = await rag_service.retrieve(query)

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Gate 2: Retrieval Confidence 검증 (OAR-12)
    gate2_result = gate2_service.validate(retrieval_result.references)

    if not gate2_result.passed:
        logger.warning(
            f"Gate 2 failed for direct RAG: {gate2_result.reason} - {gate2_result.message}"
        )
        task_result = TaskResult(
            task_id="direct_rag",
            content=gate2_result.message or "검색 결과 품질이 기준에 미달합니다.",
            references=retrieval_result.references,  # 참조는 전달 (경고와 함께)
            duration_ms=duration_ms,
            gate2_passed=False,
            gate2_reason=gate2_result.reason.value if gate2_result.reason else None,
        )
    else:
        task_result = TaskResult(
            task_id="direct_rag",
            content=retrieval_result.context,
            references=retrieval_result.references,
            duration_ms=duration_ms,
            gate2_passed=True,
        )

    # Create a pseudo-subtask for metadata
    direct_task = SubTask(
        id="direct_rag",
        query=query,
        reasoning="Direct RAG search for simple query",
        tool=ToolType.RAG_SEARCH,
        depends_on=[],
        status="completed",
    )

    return {
        "subtasks": [direct_task],
        "execution_plan": ["direct_rag"],
        "task_results": {"direct_rag": task_result},
    }
