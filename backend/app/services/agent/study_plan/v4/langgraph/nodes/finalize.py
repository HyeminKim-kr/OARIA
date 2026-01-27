"""Finalize node for LangGraph agent.

This node completes the agent execution and prepares
the final result.
"""

import logging
from datetime import datetime, timezone

from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState

logger = logging.getLogger(__name__)


def finalize_node(state: StudyPlanState) -> dict:
    """Finalize agent execution and prepare final result.

    Creates the final result structure with all gathered data
    and emits completion events.

    Args:
        state: Current LangGraph state

    Returns:
        Updated state with completion information
    """
    iteration = state.get("iteration_count", 0)
    goal_achieved = state.get("goal_achieved", False)

    logger.info(f"=== Finalize Node (iteration {iteration}) ===")
    logger.info(f"Goal achieved: {goal_achieved}")

    # Calculate total duration (approximate from execution trace)
    total_duration_ms = 0
    execution_trace = state.get("execution_trace") or []
    for step in execution_trace:
        total_duration_ms += step.get("duration_ms", 0)

    # Get token usage
    cumulative_tokens = state.get("cumulative_tokens") or {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }

    # Estimate cost (approximate based on GPT-4 pricing)
    estimated_cost = _estimate_cost(cumulative_tokens)

    # Determine final status
    force_complete = state.get("force_complete", False)
    force_reason = state.get("force_reason")

    if goal_achieved and not force_complete:
        final_status = "completed"
    elif force_complete:
        final_status = "force_completed"
    else:
        final_status = "incomplete"

    # Build final result summary
    experiments = state.get("experiments") or []
    plan_a = state.get("plan_a")
    plan_b = state.get("plan_b")

    # Create completion event for streaming
    completion_event = (
        "completion",
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": final_status,
            "goal_achieved": goal_achieved,
            "force_complete": force_complete,
            "force_reason": force_reason,
            "iteration_count": iteration,
            "total_duration_ms": total_duration_ms,
            "experiment_count": len(experiments),
            "has_plan_a": plan_a is not None,
            "has_plan_b": plan_b is not None,
            "quality_score": state.get("quality_score", 0.0),
            "cumulative_tokens": cumulative_tokens,
            "estimated_cost": estimated_cost,
        },
    )

    # Create final result event with actual plans
    result_event = (
        "result",
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "plan_a": plan_a,
            "plan_b": plan_b,
            "executive_summary": state.get("executive_summary"),
            "experiments": experiments,
            "quality_score": state.get("quality_score", 0.0),
        },
    )

    # Get existing events and add new ones
    pending_events = list(state.get("pending_events") or [])
    pending_events.extend([completion_event, result_event])

    logger.info(f"Finalization complete: status={final_status}")
    logger.info(f"Total iterations: {iteration}")
    logger.info(f"Total duration: {total_duration_ms}ms")
    logger.info(f"Experiments designed: {len(experiments)}")
    logger.info(f"Plan A: {'Yes' if plan_a else 'No'}")
    logger.info(f"Plan B: {'Yes' if plan_b else 'No'}")

    return {
        "final_status": final_status,
        "total_duration_ms": total_duration_ms,
        "estimated_cost": estimated_cost,
        "pending_events": pending_events,
        # For backwards compatibility with v3
        "final_plan": plan_a,
    }


def _estimate_cost(tokens: dict) -> float:
    """Estimate cost based on token usage.

    Uses approximate GPT-4 pricing:
    - Prompt: $0.03 / 1K tokens
    - Completion: $0.06 / 1K tokens

    Args:
        tokens: Dict with prompt_tokens and completion_tokens

    Returns:
        Estimated cost in USD
    """
    prompt_tokens = tokens.get("prompt_tokens", 0)
    completion_tokens = tokens.get("completion_tokens", 0)

    prompt_cost = (prompt_tokens / 1000) * 0.03
    completion_cost = (completion_tokens / 1000) * 0.06

    return prompt_cost + completion_cost
