"""Initialize node for LangGraph agent.

This node sets up the initial state for the agent execution.
"""

import logging
import uuid
from datetime import datetime, timezone

from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState

logger = logging.getLogger(__name__)


def initialize_node(state: StudyPlanState) -> dict:
    """Initialize the agent state.

    Sets up run metadata, validates input, and prepares
    the state for the reasoning loop.

    Args:
        state: Current state (may have user inputs)

    Returns:
        Updated state fields
    """
    logger.info("=== Initialize Node ===")

    # Generate run ID if not provided
    run_id = state.get("run_id") or str(uuid.uuid4())

    # Initialize counters
    iteration_count = 0
    consecutive_failures = 0

    # Initialize token tracking
    cumulative_tokens = state.get("cumulative_tokens") or {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    # Validate required inputs
    hypothesis = state.get("original_hypothesis", "")
    if not hypothesis:
        logger.warning("No hypothesis provided, agent may have limited functionality")

    goal = state.get("goal") or "Create a comprehensive study plan for the given hypothesis"

    # Create initialization event for streaming
    init_event = (
        "initialization",
        {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hypothesis": hypothesis[:200] + "..." if len(hypothesis) > 200 else hypothesis,
            "goal": goal,
        },
    )

    # Get existing events and add init event
    pending_events = list(state.get("pending_events") or [])
    pending_events.append(init_event)

    logger.info(f"Initialized run: {run_id[:8]}...")
    logger.info(f"Goal: {goal[:100]}...")
    logger.info(f"Hypothesis length: {len(hypothesis)} chars")

    return {
        "run_id": run_id,
        "goal": goal,
        "iteration_count": iteration_count,
        "consecutive_failures": consecutive_failures,
        "cumulative_tokens": cumulative_tokens,
        "goal_achieved": False,
        "action_success": True,  # Start optimistically
        "pending_events": pending_events,
        # Initialize empty collections if not present
        "retrieved_papers": state.get("retrieved_papers") or [],
        "evidence_snippets": state.get("evidence_snippets") or [],
        "experiments": state.get("experiments") or [],
        "measurements": state.get("measurements") or [],
        "validation_results": state.get("validation_results") or [],
        "execution_trace": state.get("execution_trace") or [],
    }
