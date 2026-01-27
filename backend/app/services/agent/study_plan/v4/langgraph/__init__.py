"""LangGraph implementation for Study Plan Agent v4.

This module provides a LangGraph StateGraph-based implementation
replacing the custom ReAct loop in core/loop.py.

Key components:
- StudyPlanState: TypedDict for graph state
- build_graph: Creates the StateGraph
- compile_graph: Compiles with optional checkpointing
- run_graph_with_streaming: Executes with SSE-compatible streaming
- Nodes: initialize, reason, execute, observe, check_goal, finalize
"""

from app.services.agent.study_plan.v4.langgraph.state import (
    StudyPlanState,
    CumulativeTokens,
    create_initial_state,
    get_state_summary,
    should_abort,
)
from app.services.agent.study_plan.v4.langgraph.graph import (
    build_graph,
    compile_graph,
    run_graph,
    run_graph_with_streaming,
)
from app.services.agent.study_plan.v4.langgraph.routing import (
    route_after_observe,
    route_after_goal_check,
    get_recovery_options,
    AgentLoopEvent,
)
from app.services.agent.study_plan.v4.langgraph.nodes import (
    initialize_node,
    observe_node,
    finalize_node,
    create_reason_node,
    create_execute_node,
    create_check_goal_node,
)

__all__ = [
    # State
    "StudyPlanState",
    "CumulativeTokens",
    "create_initial_state",
    "get_state_summary",
    "should_abort",
    # Graph
    "build_graph",
    "compile_graph",
    "run_graph",
    "run_graph_with_streaming",
    # Routing
    "route_after_observe",
    "route_after_goal_check",
    "get_recovery_options",
    "AgentLoopEvent",
    # Nodes (direct)
    "initialize_node",
    "observe_node",
    "finalize_node",
    # Node factories (require dependencies)
    "create_reason_node",
    "create_execute_node",
    "create_check_goal_node",
]
