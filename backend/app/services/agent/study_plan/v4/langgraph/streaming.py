"""Streaming adapter for LangGraph agent.

Converts LangGraph execution events to SSE-compatible events
that match the existing frontend expectations.
"""

import json
import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Any

from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState
from app.services.agent.study_plan.v4.constants import AgentEventType

logger = logging.getLogger(__name__)


# Alias for backwards compatibility
SSEEventType = AgentEventType


# ============================================================================
# Event Formatters
# ============================================================================

def format_sse_event(event_type: str | AgentEventType, data: dict) -> str:
    """Format event as SSE string.

    Args:
        event_type: Event type name (string or enum)
        data: Event data dictionary

    Returns:
        SSE-formatted string
    """
    # Convert enum to string value if needed
    if hasattr(event_type, 'value'):
        event_type = event_type.value
    json_data = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def create_initialization_event(state: StudyPlanState) -> dict:
    """Create initialization event data."""
    return {
        "run_id": state.get("run_id", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": state.get("original_hypothesis", "")[:200],
        "goal": state.get("goal", ""),
    }


def create_completion_event(state: StudyPlanState) -> dict:
    """Create completion event data.

    NOTE: Must include plan_a, plan_b, executive_summary for agent_job_executor.py
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": state.get("final_status", "completed"),
        "goal_achieved": state.get("goal_achieved", False),
        "success": state.get("goal_achieved", False),  # For agent_job_executor
        "iteration_count": state.get("iteration_count", 0),
        "total_duration_ms": state.get("total_duration_ms", 0),
        "experiment_count": len(state.get("experiments") or []),
        "has_plan_a": state.get("plan_a") is not None,
        "has_plan_b": state.get("plan_b") is not None,
        "quality_score": state.get("quality_score", 0.0),
        "cumulative_tokens": state.get("cumulative_tokens"),
        "estimated_cost": state.get("estimated_cost", 0.0),
        # Include actual data for agent_job_executor.py
        "plan_a": state.get("plan_a", ""),
        "plan_b": state.get("plan_b", ""),
        "executive_summary": state.get("executive_summary", ""),
        "experiments": state.get("experiments") or [],
    }


def create_result_event(state: StudyPlanState) -> dict:
    """Create result event data."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "plan_a": state.get("plan_a"),
        "plan_b": state.get("plan_b"),
        "executive_summary": state.get("executive_summary"),
        "experiments": state.get("experiments") or [],
        "quality_score": state.get("quality_score", 0.0),
    }


def create_error_event(error: str, state: StudyPlanState | None = None) -> dict:
    """Create error event data."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": error,
        "iteration": state.get("iteration_count", 0) if state else 0,
        "recoverable": True,
    }


# ============================================================================
# Streaming Adapter
# ============================================================================

async def stream_with_events(
    compiled_graph,
    initial_state: dict,
    config: dict = None,
) -> AsyncIterator[str]:
    """Stream LangGraph execution as SSE events.

    Converts LangGraph output to SSE-formatted strings
    compatible with the frontend.

    Args:
        compiled_graph: Compiled LangGraph StateGraph
        initial_state: Initial state dictionary
        config: Optional execution config

    Yields:
        SSE-formatted event strings
    """
    config = config or {}
    emitted_events = set()

    logger.info(f"Starting LangGraph stream with config: {config}")

    # Emit initialization event
    yield format_sse_event(
        SSEEventType.INITIALIZATION,
        create_initialization_event(initial_state),
    )

    try:
        # Run the graph and stream events
        final_state = None

        import sys
        print("[STREAMING] Starting astream loop", file=sys.stderr, flush=True)

        async for event in compiled_graph.astream(initial_state, config=config):
            for node_name, output in event.items():
                print(f"[STREAMING] Node '{node_name}' produced output", file=sys.stderr, flush=True)
                logger.debug(f"Node '{node_name}' produced output")

                # Skip if output is None (some nodes may not produce output)
                if output is None:
                    logger.debug(f"Node '{node_name}' produced None output, skipping")
                    continue

                # Extract pending events from node output
                pending_events = output.get("pending_events", [])

                for i, (event_type, event_data) in enumerate(pending_events):
                    # Create unique key to avoid duplicate events
                    event_key = (
                        event_type,
                        event_data.get("iteration", 0),
                        event_data.get("timestamp", ""),
                    )

                    if event_key not in emitted_events:
                        emitted_events.add(event_key)
                        yield format_sse_event(event_type, event_data)

                # Track final state
                final_state = {**initial_state, **output}

        # Emit final completion and result events
        print("[STREAMING] astream loop completed!", file=sys.stderr, flush=True)
        print(f"[STREAMING] final_state exists: {final_state is not None}", file=sys.stderr, flush=True)

        if final_state:
            print(f"[STREAMING] final_state keys: {list(final_state.keys())[:10]}...", file=sys.stderr, flush=True)
            print(f"[STREAMING] Emitting COMPLETED event", file=sys.stderr, flush=True)
            yield format_sse_event(
                SSEEventType.COMPLETED,
                create_completion_event(final_state),
            )
            print(f"[STREAMING] Emitting RESULT event", file=sys.stderr, flush=True)
            yield format_sse_event(
                SSEEventType.RESULT,
                create_result_event(final_state),
            )
            print(f"[STREAMING] COMPLETION and RESULT events emitted!", file=sys.stderr, flush=True)

        logger.info(f"Stream completed. Events emitted: {len(emitted_events)}")
        print(f"[STREAMING] Stream completed. Total events: {len(emitted_events)}", file=sys.stderr, flush=True)

    except Exception as e:
        import sys
        print(f"[STREAMING] EXCEPTION: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        logger.error(f"Stream error: {e}", exc_info=True)
        yield format_sse_event(
            SSEEventType.ERROR,
            create_error_event(str(e)),
        )
        raise


async def stream_to_callback(
    compiled_graph,
    initial_state: dict,
    callback,
    config: dict = None,
) -> StudyPlanState:
    """Stream LangGraph execution with callback for each event.

    Useful for integrating with existing event handlers.

    Args:
        compiled_graph: Compiled LangGraph StateGraph
        initial_state: Initial state dictionary
        callback: Async function to call for each event
        config: Optional execution config

    Returns:
        Final state after execution
    """
    config = config or {}
    final_state = dict(initial_state)

    async for sse_event in stream_with_events(compiled_graph, initial_state, config):
        # Parse SSE event
        lines = sse_event.strip().split("\n")
        event_type = None
        event_data = None

        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                event_data = json.loads(line[6:])

        if event_type and event_data:
            await callback(event_type, event_data)

            # Update final state from result event
            if event_type == SSEEventType.RESULT:
                final_state.update(event_data)

    return final_state


# ============================================================================
# Legacy Adapter (for gradual migration)
# ============================================================================

def convert_pending_events_to_sse(
    pending_events: list[tuple[str, dict]],
) -> list[str]:
    """Convert pending events list to SSE strings.

    Useful for batch conversion of events.

    Args:
        pending_events: List of (event_type, event_data) tuples

    Returns:
        List of SSE-formatted strings
    """
    return [
        format_sse_event(event_type, event_data)
        for event_type, event_data in pending_events
    ]


class LegacyEventAdapter:
    """Adapter for converting v3-style events to v4 format.

    Used during gradual migration to ensure backwards compatibility.
    """

    def __init__(self):
        self._event_buffer = []

    def push_v3_event(self, event_type: str, data: dict) -> None:
        """Push a v3-style event to the buffer."""
        # Convert v3 event types to v4
        type_mapping = {
            "thinking": SSEEventType.REASONING,
            "action": SSEEventType.ACTING,
            "tool_call": SSEEventType.ACTING,
            "tool_result": SSEEventType.OBSERVATION,
            "done": SSEEventType.COMPLETED,
        }

        v4_type = type_mapping.get(event_type, event_type)
        self._event_buffer.append((v4_type, data))

    def get_sse_events(self) -> list[str]:
        """Get all buffered events as SSE strings."""
        events = convert_pending_events_to_sse(self._event_buffer)
        self._event_buffer.clear()
        return events

    def clear(self) -> None:
        """Clear the event buffer."""
        self._event_buffer.clear()
