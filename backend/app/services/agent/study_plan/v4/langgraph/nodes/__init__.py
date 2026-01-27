"""LangGraph nodes for Study Plan Agent v4.

Each node represents a step in the agent's execution flow:
- initialize: Set up initial state
- reason: Decide next action (wraps Reasoner)
- execute: Run the action (wraps Executor)
- observe: Process the result
- check_goal: Evaluate progress (wraps GoalChecker)
- finalize: Complete execution

Note: reason, execute, and check_goal use factory functions
to inject dependencies (Reasoner, Executor, GoalChecker).
"""

from app.services.agent.study_plan.v4.langgraph.nodes.initialize import initialize_node
from app.services.agent.study_plan.v4.langgraph.nodes.reason import create_reason_node
from app.services.agent.study_plan.v4.langgraph.nodes.execute import create_execute_node
from app.services.agent.study_plan.v4.langgraph.nodes.observe import observe_node
from app.services.agent.study_plan.v4.langgraph.nodes.check_goal import create_check_goal_node
from app.services.agent.study_plan.v4.langgraph.nodes.finalize import finalize_node

__all__ = [
    # Direct nodes (no dependencies)
    "initialize_node",
    "observe_node",
    "finalize_node",
    # Factory functions (require dependencies)
    "create_reason_node",
    "create_execute_node",
    "create_check_goal_node",
]
