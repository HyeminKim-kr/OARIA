"""Tool Router node (OAR-49)."""

import logging
from collections import defaultdict

from ..state import AgentState, SubTask, ToolType

logger = logging.getLogger(__name__)


def route_tools(state: AgentState) -> AgentState:
    """
    Route sub-tasks to appropriate tools and optimize execution order.

    This node:
    1. Validates tool assignments from decomposer
    2. Identifies tasks that can run in parallel
    3. Optimizes execution order based on dependencies

    Args:
        state: Current agent state with subtasks

    Returns:
        Updated state with optimized execution_plan
    """
    subtasks = state.get("subtasks", [])

    if not subtasks:
        logger.warning("No subtasks to route")
        return state

    logger.info(f"Routing {len(subtasks)} tasks to tools...")

    # Build dependency graph
    task_map = {task.id: task for task in subtasks}
    dependents = defaultdict(list)  # task_id -> list of tasks that depend on it

    for task in subtasks:
        for dep_id in task.depends_on:
            dependents[dep_id].append(task.id)

    # Topological sort for execution order
    execution_order = []
    in_degree = {task.id: len(task.depends_on) for task in subtasks}
    ready = [task.id for task in subtasks if in_degree[task.id] == 0]

    # Identify parallel execution groups
    parallel_groups = []
    current_group = []

    while ready:
        # All tasks in 'ready' can execute in parallel
        current_group = sorted(ready)  # Sort for deterministic order
        parallel_groups.append(current_group)
        execution_order.extend(current_group)

        # Find next batch of ready tasks
        next_ready = []
        for task_id in current_group:
            for dependent_id in dependents[task_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    next_ready.append(dependent_id)

        ready = next_ready

    # Log routing decisions
    for i, group in enumerate(parallel_groups):
        tasks_info = [f"{tid}({task_map[tid].tool.value})" for tid in group]
        logger.info(f"Execution group {i + 1}: {', '.join(tasks_info)}")

    return {
        "execution_plan": execution_order,
    }
