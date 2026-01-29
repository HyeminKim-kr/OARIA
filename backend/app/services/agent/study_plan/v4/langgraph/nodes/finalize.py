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
    import sys
    print("\n" + "="*70, file=sys.stderr, flush=True)
    print("[FINALIZE NODE CALLED]", file=sys.stderr, flush=True)
    print("="*70 + "\n", file=sys.stderr, flush=True)

    iteration = state.get("iteration_count", 0)
    goal_achieved = state.get("goal_achieved", False)

    print(f"[FINALIZE] iteration={iteration}, goal_achieved={goal_achieved}", file=sys.stderr, flush=True)
    print(f"[FINALIZE] plan_a exists: {state.get('plan_a') is not None}", file=sys.stderr, flush=True)
    print(f"[FINALIZE] plan_b exists: {state.get('plan_b') is not None}", file=sys.stderr, flush=True)

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
    retrieved_papers = state.get("retrieved_papers") or []
    evidence_snippets = state.get("evidence_snippets") or []

    print(f"[FINALIZE] retrieved_papers count: {len(retrieved_papers)}", file=sys.stderr, flush=True)
    print(f"[FINALIZE] evidence_snippets count: {len(evidence_snippets)}", file=sys.stderr, flush=True)

    # Create completion event for streaming
    # NOTE: Must use "completed" to match AgentEventType.COMPLETED
    # NOTE: Must include plan_a, plan_b, executive_summary for agent_job_executor.py
    completion_event = (
        "completed",
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": final_status,
            "goal_achieved": goal_achieved,
            "success": goal_achieved,  # For agent_job_executor
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
            # Required by agent_job_executor.py
            "plan_a": plan_a or "",
            "plan_b": plan_b or "",
            "executive_summary": state.get("executive_summary") or "",
            # Papers and evidence for citations
            "retrieved_papers": retrieved_papers,
            "evidence_snippets": evidence_snippets,
            "paper_count": len(retrieved_papers),
            "snippet_count": len(evidence_snippets),
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
            # Papers and evidence for citations
            "retrieved_papers": retrieved_papers,
            "evidence_snippets": evidence_snippets,
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

    import sys
    print(f"[FINALIZE] About to return. pending_events count: {len(pending_events)}", file=sys.stderr, flush=True)
    print(f"[FINALIZE] final_status={final_status}", file=sys.stderr, flush=True)
    print("="*70 + "\n", file=sys.stderr, flush=True)

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
