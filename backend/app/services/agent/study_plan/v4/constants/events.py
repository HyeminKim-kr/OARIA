"""Centralized event types for Study Plan Agent v4.

This is the single source of truth for all event type constants.
Frontend should have matching TypeScript definitions.

Usage:
    from app.services.agent.study_plan.v4.constants import AgentEventType

    if event_type == AgentEventType.COMPLETED:
        ...
"""

from enum import Enum


class AgentEventType(str, Enum):
    """Agent SSE event types.

    These must match the frontend TypeScript definitions in:
    frontend/src/app/agents/study-plan/constants/events.ts
    """

    # Lifecycle events
    INITIALIZATION = "initialization"
    STARTED = "started"
    COMPLETED = "completed"
    ERROR = "error"

    # Reasoning/Action events
    THINKING = "thinking"      # LLM reasoning
    REASONING = "reasoning"    # Alias for thinking
    ACTING = "acting"          # Action being executed
    OBSERVATION = "observation"  # Action result

    # Goal/Recovery events
    GOAL_CHECK = "goal_check"
    RECOVERY = "recovery"
    USER_INPUT_REQUEST = "user_input_request"

    # Result events
    RESULT = "result"


class NodeStatus(str, Enum):
    """Node/step status values.

    Used for tracking progress of individual steps.
    """

    PENDING = "pending"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"


class JobStatus(str, Enum):
    """Agent job status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# For backwards compatibility - aliases
SSEEventType = AgentEventType
AgentLoopEvent = AgentEventType
