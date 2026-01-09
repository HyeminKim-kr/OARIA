"""Task Decomposer node (OAR-48)."""

import json
import logging

from openai import OpenAI

from app.config import settings
from ..state import AgentState, SubTask, ToolType
from ..prompts import TASK_DECOMPOSER_SYSTEM, TASK_DECOMPOSER_USER

logger = logging.getLogger(__name__)


def decompose_tasks(state: AgentState) -> AgentState:
    """
    Decompose a complex query into sub-tasks.

    This node uses GPT-4o-mini to break down the query into
    2-5 executable sub-tasks with dependencies.

    Args:
        state: Current agent state with query and complexity

    Returns:
        Updated state with subtasks and execution_plan
    """
    query = state["query"]
    complexity = state.get("complexity", "complex")
    complexity_reasoning = state.get("complexity_reasoning", "")

    logger.info(f"Decomposing query into sub-tasks: {query[:100]}...")

    client = OpenAI(api_key=settings.openai_api_key)

    try:
        response = client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {"role": "system", "content": TASK_DECOMPOSER_SYSTEM},
                {
                    "role": "user",
                    "content": TASK_DECOMPOSER_USER.format(
                        query=query,
                        complexity=complexity.value
                        if hasattr(complexity, "value")
                        else complexity,
                        complexity_reasoning=complexity_reasoning,
                    ),
                },
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        tasks_data = result.get("tasks", [])
        execution_plan = result.get("execution_plan", [])

        # Convert to SubTask objects
        tool_map = {
            "rag_search": ToolType.RAG_SEARCH,
            "compare": ToolType.COMPARE,
            "summarize": ToolType.SUMMARIZE,
        }

        subtasks = []
        seen_queries = set()  # For deduplication

        for task_data in tasks_data:
            query_text = task_data.get("query", "").strip().lower()

            # Skip duplicate queries (similarity check)
            is_duplicate = False
            for seen_q in seen_queries:
                # Check if queries are very similar (>80% overlap in words)
                words1 = set(query_text.split())
                words2 = set(seen_q.split())
                if words1 and words2:
                    overlap = len(words1 & words2) / max(len(words1), len(words2))
                    if overlap > 0.8:
                        logger.warning(f"Skipping duplicate task: {query_text[:50]}...")
                        is_duplicate = True
                        break

            if is_duplicate:
                continue

            seen_queries.add(query_text)

            tool_str = task_data.get("tool", "rag_search").lower()
            tool = tool_map.get(tool_str, ToolType.RAG_SEARCH)

            subtask = SubTask(
                id=task_data.get("id", f"task_{len(subtasks) + 1}"),
                query=task_data.get("query", ""),
                reasoning=task_data.get("reasoning", ""),
                tool=tool,
                depends_on=task_data.get("depends_on", []),
            )
            subtasks.append(subtask)

        # Limit to max 5 tasks
        if len(subtasks) > 5:
            logger.warning(f"Too many tasks ({len(subtasks)}), limiting to 5")
            subtasks = subtasks[:5]

        # ENSURE last task is summarize (mandatory)
        if subtasks and subtasks[-1].tool != ToolType.SUMMARIZE:
            logger.warning("Last task is not summarize, adding one")
            # Get all task IDs for dependencies
            all_task_ids = [t.id for t in subtasks]
            summarize_task = SubTask(
                id=f"task_{len(subtasks) + 1}",
                query=f"Summarize all findings for: {query[:100]}",
                reasoning="Final synthesis of all gathered information",
                tool=ToolType.SUMMARIZE,
                depends_on=all_task_ids,
            )
            subtasks.append(summarize_task)

        # ENSURE second-to-last task is compare (if we have enough tasks)
        if len(subtasks) >= 2 and subtasks[-2].tool != ToolType.COMPARE:
            # Check if there's a compare task anywhere
            compare_tasks = [t for t in subtasks if t.tool == ToolType.COMPARE]
            if not compare_tasks and len(subtasks) >= 3:
                logger.warning("No compare task found, adding one before summarize")
                # Get RAG task IDs for dependencies
                rag_task_ids = [t.id for t in subtasks if t.tool == ToolType.RAG_SEARCH]
                compare_task = SubTask(
                    id=f"task_compare",
                    query=f"Compare and analyze differences for: {query[:80]}",
                    reasoning="Comparison analysis of gathered information",
                    tool=ToolType.COMPARE,
                    depends_on=rag_task_ids,
                )
                # Insert before the last task (summarize)
                subtasks.insert(-1, compare_task)
                # Update summarize task to depend on compare
                subtasks[-1].depends_on.append(compare_task.id)

        # Ensure execution_plan includes all tasks
        if not execution_plan:
            execution_plan = [t.id for t in subtasks]
        else:
            # Filter execution plan to only include existing task IDs
            valid_ids = {t.id for t in subtasks}
            execution_plan = [tid for tid in execution_plan if tid in valid_ids]
            # Add any missing task IDs
            for t in subtasks:
                if t.id not in execution_plan:
                    execution_plan.append(t.id)

        logger.info(f"Decomposed into {len(subtasks)} sub-tasks (after deduplication)")

        return {
            "subtasks": subtasks,
            "execution_plan": execution_plan,
        }

    except Exception as e:
        logger.error(f"Error decomposing tasks: {e}")
        # Create a single RAG task as fallback
        fallback_task = SubTask(
            id="task_1",
            query=query,
            reasoning="Fallback to single search due to decomposition error",
            tool=ToolType.RAG_SEARCH,
            depends_on=[],
        )
        return {
            "subtasks": [fallback_task],
            "execution_plan": ["task_1"],
            "error": f"Task decomposition error: {str(e)}",
        }
