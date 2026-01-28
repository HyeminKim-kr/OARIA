"""Check goal node for LangGraph agent.

This node wraps the existing GoalChecker component to evaluate
whether the agent has achieved its goal.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState
from app.services.agent.study_plan.v4.core.state_view import StateView

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.core.goal_checker import GoalChecker

logger = logging.getLogger(__name__)

# Maximum iterations before forcing completion
MAX_ITERATIONS = 30


def create_check_goal_node(goal_checker: "GoalChecker"):
    """Factory function to create a check_goal node with injected dependencies.

    Args:
        goal_checker: The GoalChecker instance to use for evaluation

    Returns:
        A function that can be used as a LangGraph node
    """

    def check_goal_node(state: StudyPlanState) -> dict:
        """Evaluate goal achievement.

        Wraps the GoalChecker component using StateView for
        read-only state access.

        Args:
            state: Current LangGraph state

        Returns:
            Updated state with goal status
        """
        import sys
        print("\n" + "="*70, file=sys.stderr, flush=True)
        print("[CHECK_GOAL NODE CALLED]", file=sys.stderr, flush=True)
        print("="*70 + "\n", file=sys.stderr, flush=True)

        iteration = state.get("iteration_count", 0)
        current_action = state.get("current_action", "")
        is_terminal = state.get("is_terminal", False)
        print(f"[CHECK_GOAL] iteration={iteration}, current_action={current_action}", file=sys.stderr, flush=True)
        print(f"[CHECK_GOAL] is_terminal={is_terminal}", file=sys.stderr, flush=True)

        logger.info(f"=== Check Goal Node (iteration {iteration}) ===")

        # Create StateView (read-only view of state)
        state_view = StateView(state)

        # Check goal status
        status = goal_checker.check(state_view)

        logger.info(f"Goal achieved: {status.achieved}")
        if not status.achieved:
            logger.info(f"Missing: {status.missing}")

        # Check for forced completion conditions
        force_complete = False
        force_reason = None

        # Check iteration limit
        if iteration >= MAX_ITERATIONS:
            force_complete = True
            force_reason = f"Maximum iterations ({MAX_ITERATIONS}) reached"
            logger.warning(force_reason)

        # Check if terminal action was executed
        if state.get("is_terminal"):
            force_complete = True
            force_reason = "Terminal action (FINISH) was executed"
            logger.info(force_reason)

        # Check consecutive failures
        consecutive_failures = state.get("consecutive_failures", 0)
        if consecutive_failures >= 5:
            force_complete = True
            force_reason = f"Too many consecutive failures ({consecutive_failures})"
            logger.warning(force_reason)

        # Determine final goal status
        goal_achieved = status.achieved or force_complete

        # Create goal check event for streaming
        goal_event = (
            "goal_check",
            {
                "iteration": iteration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "achieved": goal_achieved,
                "missing": status.missing if not status.achieved else [],
                "details": status.details,
                "force_complete": force_complete,
                "force_reason": force_reason,
                "quality_assessment": status.quality_assessment,
            },
        )

        # Get existing events and add new one
        pending_events = list(state.get("pending_events") or [])
        pending_events.append(goal_event)

        # Get next priority if not achieved
        next_priority = None
        if not goal_achieved:
            next_priority = goal_checker.get_next_priority(state_view)

        import sys
        print(f"[CHECK_GOAL] goal_achieved={goal_achieved}, force_complete={force_complete}", file=sys.stderr, flush=True)
        print(f"[CHECK_GOAL] status.achieved={status.achieved}", file=sys.stderr, flush=True)
        print(f"[CHECK_GOAL] missing={status.missing}", file=sys.stderr, flush=True)
        print(f"[CHECK_GOAL] RETURNING goal_achieved={goal_achieved}", file=sys.stderr, flush=True)
        print(f"[CHECK_GOAL] pending_events count: {len(pending_events)}", file=sys.stderr, flush=True)
        print("="*70 + "\n", file=sys.stderr, flush=True)

        return {
            "goal_achieved": goal_achieved,
            "goal_details": status.details,
            "goals_missing": status.missing,
            "quality_assessment": status.quality_assessment,
            "next_priority": next_priority,
            "force_complete": force_complete,
            "force_reason": force_reason,
            "pending_events": pending_events,
        }

    return check_goal_node
