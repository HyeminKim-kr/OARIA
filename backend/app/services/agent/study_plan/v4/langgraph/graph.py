"""LangGraph StateGraph builder for Study Plan Agent v4.

Assembles the agent graph using StateGraph with conditional routing.

Graph structure:
    START → initialize → reason ←──────┐
                           ↓           │
                        execute        │
                           ↓           │
                        observe        │
                           ↓           │
                      check_goal ──────┘ (continue)
                           ↓ (done/error)
                       finalize → END
"""

import logging
from typing import TYPE_CHECKING

from langgraph.graph import StateGraph, START, END

from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState
from app.services.agent.study_plan.v4.langgraph.routing import (
    route_after_observe,
    route_after_goal_check,
)
from app.services.agent.study_plan.v4.langgraph.nodes import (
    initialize_node,
    observe_node,
    finalize_node,
)
from app.services.agent.study_plan.v4.langgraph.nodes.reason import create_reason_node
from app.services.agent.study_plan.v4.langgraph.nodes.execute import create_execute_node
from app.services.agent.study_plan.v4.langgraph.nodes.check_goal import create_check_goal_node

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.core.reasoner import Reasoner
    from app.services.agent.study_plan.v4.core.executor import Executor
    from app.services.agent.study_plan.v4.core.goal_checker import GoalChecker

logger = logging.getLogger(__name__)


def build_graph(
    reasoner: "Reasoner",
    executor: "Executor",
    goal_checker: "GoalChecker",
) -> StateGraph:
    """Build the LangGraph StateGraph for the Study Plan Agent.

    Creates a compiled graph with all nodes and edges configured.

    Args:
        reasoner: Reasoner instance for action decisions
        executor: Executor instance for running actions
        goal_checker: GoalChecker instance for evaluating progress

    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Building LangGraph StateGraph...")

    # Create the graph with our state type
    graph = StateGraph(StudyPlanState)

    # Create node functions with injected dependencies
    reason_node = create_reason_node(reasoner)
    execute_node = create_execute_node(executor)
    check_goal_node = create_check_goal_node(goal_checker)

    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("reason", reason_node)
    graph.add_node("execute", execute_node)
    graph.add_node("observe", observe_node)
    graph.add_node("check_goal", check_goal_node)
    graph.add_node("finalize", finalize_node)

    # Add edges

    # START → initialize
    graph.add_edge(START, "initialize")

    # initialize → reason
    graph.add_edge("initialize", "reason")

    # reason → execute
    graph.add_edge("reason", "execute")

    # execute → observe
    graph.add_edge("execute", "observe")

    # observe → check_goal OR finalize (conditional)
    # If terminal action (FINISH) was executed, go directly to finalize
    graph.add_conditional_edges(
        "observe",
        route_after_observe,
        {
            "check_goal": "check_goal",
            "finalize": "finalize",
        }
    )

    # check_goal → reason OR finalize (conditional)
    # Continue if goal not achieved, finalize if achieved or max iterations
    graph.add_conditional_edges(
        "check_goal",
        route_after_goal_check,
        {
            "reason": "reason",
            "finalize": "finalize",
        }
    )

    # finalize → END
    graph.add_edge("finalize", END)

    logger.info("StateGraph built successfully")

    return graph


def compile_graph(
    reasoner: "Reasoner",
    executor: "Executor",
    goal_checker: "GoalChecker",
    checkpointer=None,
):
    """Build and compile the graph with optional checkpointing.

    Args:
        reasoner: Reasoner instance
        executor: Executor instance
        goal_checker: GoalChecker instance
        checkpointer: Optional checkpointer for persistence

    Returns:
        Compiled graph ready for execution

    Note:
        recursion_limit should be set via config at runtime, not compile time.
        Use create_thread_config() with recursion_limit parameter.
    """
    graph = build_graph(reasoner, executor, goal_checker)

    compile_kwargs = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer

    compiled = graph.compile(**compile_kwargs)

    logger.info("Graph compiled successfully")
    return compiled


async def run_graph(
    compiled_graph,
    initial_state: dict,
    config: dict = None,
):
    """Run the compiled graph with initial state.

    This is a convenience function for running the graph
    and collecting all events.

    Args:
        compiled_graph: Compiled StateGraph
        initial_state: Initial state dictionary
        config: Optional config for the run

    Yields:
        Tuples of (event_type, event_data) as the graph executes
    """
    config = config or {}

    logger.info(f"Running graph with config: {config}")

    # Run the graph
    async for event in compiled_graph.astream(initial_state, config=config):
        # LangGraph yields node outputs as {node_name: output_dict}
        for node_name, output in event.items():
            logger.debug(f"Node '{node_name}' completed")

            # Extract and yield pending events
            pending_events = output.get("pending_events", [])
            for event_type, event_data in pending_events:
                yield (event_type, event_data)


async def run_graph_with_streaming(
    compiled_graph,
    initial_state: dict,
    config: dict = None,
):
    """Run the graph and yield streaming events.

    This function provides SSE-compatible streaming by yielding
    events as they occur during execution.

    Args:
        compiled_graph: Compiled StateGraph
        initial_state: Initial state dictionary
        config: Optional config for the run

    Yields:
        Tuples of (event_type, event_data) for SSE streaming
    """
    config = config or {}

    # Track already-emitted events
    emitted_events = set()

    async for event in compiled_graph.astream(initial_state, config=config):
        for node_name, output in event.items():
            # Extract pending events
            pending_events = output.get("pending_events", [])

            # Emit only new events
            for i, (event_type, event_data) in enumerate(pending_events):
                # Create a unique key for this event
                event_key = (event_type, event_data.get("iteration", 0), i)

                if event_key not in emitted_events:
                    emitted_events.add(event_key)
                    yield (event_type, event_data)

    logger.info(f"Graph execution completed. Total events emitted: {len(emitted_events)}")
