"""Executor node (OAR-50)."""

import asyncio
import logging
import time
from collections import defaultdict

from openai import OpenAI

from app.config import settings
from app.services.rag_service import rag_service
from app.schemas.chat import Reference
from ..state import AgentState, SubTask, TaskResult, ToolType
from ..prompts import COMPARE_SYSTEM, COMPARE_USER

logger = logging.getLogger(__name__)


def execute_tasks(state: AgentState) -> AgentState:
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
        # Execute ready tasks (could be parallelized with asyncio.gather)
        for task_id in ready:
            task = task_map[task_id]
            logger.info(f"Executing task {task_id}: {task.query[:50]}...")

            try:
                result = _execute_single_task(task, task_results)
                task_results[task_id] = result
                logger.info(
                    f"Task {task_id} completed in {result.duration_ms}ms "
                    f"with {len(result.references)} references"
                )
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                task_results[task_id] = TaskResult(
                    task_id=task_id,
                    content="",
                    references=[],
                    error=str(e),
                )

        # Find next batch of ready tasks
        next_ready = []
        for task_id in ready:
            for dependent_id in dependents[task_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    next_ready.append(dependent_id)

        ready = next_ready

    return {"task_results": task_results}


def _execute_single_task(
    task: SubTask, previous_results: dict[str, TaskResult]
) -> TaskResult:
    """Execute a single task based on its tool type."""
    start_time = time.perf_counter()

    if task.tool == ToolType.RAG_SEARCH:
        result = _execute_rag_search(task)
    elif task.tool == ToolType.COMPARE:
        result = _execute_compare(task, previous_results)
    elif task.tool == ToolType.SUMMARIZE:
        result = _execute_summarize(task, previous_results)
    else:
        # Fallback to RAG search
        result = _execute_rag_search(task)

    result.duration_ms = int((time.perf_counter() - start_time) * 1000)
    return result


def _execute_rag_search(task: SubTask) -> TaskResult:
    """Execute RAG search using existing rag_service."""
    retrieval_result = rag_service.retrieve(task.query)

    return TaskResult(
        task_id=task.id,
        content=retrieval_result.context,
        references=retrieval_result.references,
    )


def _execute_compare(
    task: SubTask, previous_results: dict[str, TaskResult]
) -> TaskResult:
    """Execute comparison using LLM with context from previous tasks."""
    # Gather context from dependent tasks
    context_parts = []
    all_references = []

    for dep_id in task.depends_on:
        if dep_id in previous_results:
            dep_result = previous_results[dep_id]
            context_parts.append(f"[{dep_id}]: {dep_result.content}")
            all_references.extend(dep_result.references)

    context = "\n\n".join(context_parts)

    # Use LLM for comparison
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
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


def execute_direct_rag(state: AgentState) -> AgentState:
    """
    Execute direct RAG for simple queries (bypasses decomposition).

    Used when complexity is SIMPLE - goes directly from
    analyze_complexity to synthesis.
    """
    query = state["query"]
    logger.info(f"Executing direct RAG for simple query: {query[:50]}...")

    start_time = time.perf_counter()

    # Use existing RAG service
    retrieval_result = rag_service.retrieve(query)

    duration_ms = int((time.perf_counter() - start_time) * 1000)

    # Create a single task result
    task_result = TaskResult(
        task_id="direct_rag",
        content=retrieval_result.context,
        references=retrieval_result.references,
        duration_ms=duration_ms,
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
