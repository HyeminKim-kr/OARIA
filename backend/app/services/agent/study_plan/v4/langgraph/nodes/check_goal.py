"""Check goal node for LangGraph agent.

This node wraps the existing GoalChecker component to evaluate
whether the agent has achieved its goal.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState
from app.services.agent.study_plan.v4.core.state import WorkingMemory

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

        Wraps the GoalChecker component, converting between
        LangGraph state and WorkingMemory.

        Args:
            state: Current LangGraph state

        Returns:
            Updated state with goal status
        """
        iteration = state.get("iteration_count", 0)
        logger.info(f"=== Check Goal Node (iteration {iteration}) ===")

        # Convert state to WorkingMemory for GoalChecker
        working_memory = _state_to_working_memory(state)

        # Check goal status
        status = goal_checker.check(working_memory)

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
            next_priority = goal_checker.get_next_priority(working_memory)

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


def _state_to_working_memory(state: StudyPlanState) -> WorkingMemory:
    """Convert LangGraph state to WorkingMemory for GoalChecker.

    This includes all fields needed for goal checking.
    """
    memory = WorkingMemory()

    # Input
    memory.run_id = state.get("run_id", memory.run_id)
    memory.goal = state.get("goal", "")
    memory.original_hypothesis = state.get("original_hypothesis", "")

    # Parsed
    memory.structured_hypothesis = state.get("structured_hypothesis")
    memory.hypothesis_confidence = state.get("hypothesis_confidence", 0.0)

    # Questions
    memory.test_questions = state.get("test_questions") or []
    memory.answered_questions = set(state.get("answered_questions") or [])

    # Search
    memory.retrieved_papers = state.get("retrieved_papers") or []
    memory.evidence_snippets = state.get("evidence_snippets") or []
    memory.search_coverage = state.get("search_coverage", 0.0)

    # Design
    memory.experiments = state.get("experiments") or []
    memory.controls = state.get("controls") or {}
    memory.measurements = state.get("measurements") or []

    # Validation
    memory.validation_results = state.get("validation_results") or []
    memory.quality_score = state.get("quality_score", 0.0)
    memory.critique_history = state.get("critique_history") or []

    # Output
    memory.plan_a = state.get("plan_a")
    memory.plan_b = state.get("plan_b")
    memory.executive_summary = state.get("executive_summary")

    # Metadata
    memory.iteration_count = state.get("iteration_count", 0)

    return memory
