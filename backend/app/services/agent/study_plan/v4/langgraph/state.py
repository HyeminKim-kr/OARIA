"""LangGraph State definition for Study Plan Agent v4.

This module defines the state TypedDict used by the LangGraph StateGraph.
It mirrors the functionality of WorkingMemory and ExecutionHistory from core/state.py.
"""

from dataclasses import dataclass, field
from typing import TypedDict, Annotated, Any
from operator import add


# ============================================================================
# Token Tracking
# ============================================================================

@dataclass
class CumulativeTokens:
    """Cumulative token usage tracking."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, usage: dict[str, int] | None) -> None:
        """Add token usage from a single LLM call."""
        if usage is None:
            return
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary for serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "CumulativeTokens":
        """Create from dictionary."""
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
        )


# ============================================================================
# Execution Step Record
# ============================================================================

@dataclass
class ExecutionStepRecord:
    """Record of a single execution step for history tracking."""

    step_number: int
    timestamp: str  # ISO format
    thought: str
    action: str
    action_input: dict[str, Any]
    observation: dict[str, Any]
    success: bool
    error: str | None = None
    duration_ms: int = 0
    token_usage: dict[str, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_number": self.step_number,
            "timestamp": self.timestamp,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "success": self.success,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "token_usage": self.token_usage,
        }


# ============================================================================
# Recovery Option
# ============================================================================

@dataclass
class RecoveryOption:
    """Recovery option for failure handling."""

    id: str
    label: str
    description: str
    risk_level: str  # "low", "medium", "high"
    estimated_time: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "risk_level": self.risk_level,
            "estimated_time": self.estimated_time,
        }


# ============================================================================
# LangGraph State TypedDict
# ============================================================================

class StudyPlanState(TypedDict, total=False):
    """LangGraph state for Study Plan Agent v4.

    This state replaces WorkingMemory and ExecutionHistory from core/state.py.
    Uses LangGraph reducers for list append operations.

    Attributes:
        # === Identification ===
        run_id: Unique run identifier
        started_at: ISO format timestamp

        # === Input ===
        goal: Agent goal description
        original_hypothesis: User's input hypothesis
        research_context: Optional research context
        constraints: List of constraints
        preferred_experiment_types: Preferred experiment types

        # === Parsed Hypothesis ===
        structured_hypothesis: Parsed hypothesis dict
        hypothesis_confidence: Confidence score 0-1

        # === Test Questions (NSPE) ===
        test_questions: Generated test questions
        answered_questions: List of addressed question IDs

        # === Search Results (append reducers) ===
        retrieved_papers: List of retrieved papers
        evidence_snippets: List of evidence snippets
        search_coverage: Coverage score 0-1
        search_tiers_used: List of search tiers used (1=RAG, 2=EPMC, 3=Web)

        # === Design Results ===
        experiments: Designed experiments
        controls: Dict of experiment_id -> controls list
        measurements: Measurement specifications

        # === Validation ===
        validation_results: Validation results
        quality_score: Overall quality score 0-1
        critique_history: History of critique rounds

        # === Output ===
        plan_a: Ideal study plan (full template)
        plan_b: Practical alternative plan
        executive_summary: Executive summary

        # === Execution Control ===
        iteration_count: Current iteration number
        max_iterations: Maximum allowed iterations
        total_cost: Accumulated cost

        # === Current Action State ===
        current_thought: LLM's reasoning for current action
        current_action: Name of current action
        current_action_input: Input for current action
        current_observation: Result of current action
        current_action_confidence: Confidence in action choice
        action_success: Whether current action succeeded

        # === Token Tracking ===
        current_token_usage: Token usage for current LLM call
        cumulative_tokens: Total accumulated token usage

        # === History & Failure Tracking ===
        execution_history: List of execution step records
        failed_actions: Dict of action -> failure count
        consecutive_failures: Count of consecutive failures
        last_error: Last error message
        same_error_count: Count of same error repetitions
        critical_error: Critical error message (if any)

        # === Goal Status ===
        goal_achieved: Whether goal is achieved
        goal_details: Dict of goal criteria -> status
        goal_missing: List of unmet goal criteria

        # === Recovery ===
        recovery_options: Available recovery options
        recovery_strategy: Selected recovery strategy

        # === Streaming Events ===
        pending_events: List of (event_type, event_data) tuples to emit
    """

    # === Identification ===
    run_id: str
    started_at: str  # ISO format

    # === Input ===
    goal: str
    original_hypothesis: str
    research_context: str | None
    constraints: list[str]
    preferred_experiment_types: list[str]

    # === Parsed Hypothesis ===
    structured_hypothesis: dict[str, Any] | None
    hypothesis_confidence: float

    # === Test Questions (NSPE) ===
    test_questions: list[dict[str, Any]]
    answered_questions: list[str]

    # === Search Results ===
    # Using Annotated with add reducer for append operations
    retrieved_papers: Annotated[list[dict[str, Any]], add]
    evidence_snippets: Annotated[list[dict[str, Any]], add]
    search_coverage: float
    search_tiers_used: Annotated[list[int], add]  # Using add reducer for consistency

    # === Design Results ===
    # NOTE: experiments is NOT using add reducer - manually accumulated in observe node
    experiments: list[dict[str, Any]]
    controls: dict[str, list[dict[str, Any]]]
    measurements: Annotated[list[dict[str, Any]], add]

    # === Validation ===
    validation_results: Annotated[list[dict[str, Any]], add]
    quality_score: float
    critique_history: Annotated[list[dict[str, Any]], add]

    # === Output ===
    plan_a: str | None
    plan_b: str | None
    executive_summary: str | None

    # === Execution Control ===
    iteration_count: int
    max_iterations: int
    total_cost: float

    # === Current Action State ===
    current_thought: str
    current_action: str
    current_action_input: dict[str, Any]
    current_observation: dict[str, Any]
    current_action_confidence: float
    action_success: bool
    action_result: Any  # Result from executor - used by observe node
    action_error: str | None  # Error from executor
    is_terminal: bool  # Whether action was terminal (FINISH)

    # === Token Tracking ===
    current_token_usage: dict[str, int] | None
    cumulative_tokens: dict[str, int]

    # === History & Failure Tracking ===
    execution_history: list[dict[str, Any]]
    failed_actions: dict[str, int]
    consecutive_failures: int
    last_error: str | None
    same_error_count: int
    critical_error: str | None

    # === Goal Status ===
    goal_achieved: bool
    goal_details: dict[str, bool]
    goal_missing: list[str]

    # === Recovery ===
    recovery_options: list[dict[str, Any]]
    recovery_strategy: str | None

    # === Streaming Events ===
    pending_events: list[tuple[str, dict[str, Any]]]


# ============================================================================
# State Factory Functions
# ============================================================================

def create_initial_state(
    hypothesis: str,
    research_context: str | None = None,
    constraints: list[str] | None = None,
    preferred_experiment_types: list[str] | None = None,
    max_iterations: int = 30,
    goal: str | None = None,
) -> StudyPlanState:
    """Create initial state for a new agent run.

    Args:
        hypothesis: The research hypothesis to test
        research_context: Optional research context
        constraints: Optional list of constraints
        preferred_experiment_types: Optional preferred experiment types
        max_iterations: Maximum iterations (default 30)
        goal: Optional custom goal (uses default if not provided)

    Returns:
        Initial StudyPlanState
    """
    import uuid
    from datetime import datetime

    default_goal = (
        "Generate a comprehensive research study plan to test the given hypothesis. "
        "The plan should include: structured hypothesis, test questions (NSPE framework), "
        "experiment designs with proper controls, measurements that cover hypothesis variables, "
        "and achieve a quality score of at least 70%."
    )

    return StudyPlanState(
        # Identification
        run_id=str(uuid.uuid4()),
        started_at=datetime.utcnow().isoformat(),

        # Input
        goal=goal or default_goal,
        original_hypothesis=hypothesis,
        research_context=research_context,
        constraints=constraints or [],
        preferred_experiment_types=preferred_experiment_types or [],

        # Parsed
        structured_hypothesis=None,
        hypothesis_confidence=0.0,

        # Test Questions
        test_questions=[],
        answered_questions=[],

        # Search
        retrieved_papers=[],
        evidence_snippets=[],
        search_coverage=0.0,
        search_tiers_used=[],

        # Design
        experiments=[],
        controls={},
        measurements=[],

        # Validation
        validation_results=[],
        quality_score=0.0,
        critique_history=[],

        # Output
        plan_a=None,
        plan_b=None,
        executive_summary=None,

        # Execution Control
        iteration_count=0,
        max_iterations=max_iterations,
        total_cost=0.0,

        # Current Action
        current_thought="",
        current_action="",
        current_action_input={},
        current_observation={},
        current_action_confidence=0.0,
        action_success=True,
        action_result=None,
        action_error=None,
        is_terminal=False,

        # Tokens
        current_token_usage=None,
        cumulative_tokens={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},

        # History
        execution_history=[],
        failed_actions={},
        consecutive_failures=0,
        last_error=None,
        same_error_count=0,
        critical_error=None,

        # Goal
        goal_achieved=False,
        goal_details={},
        goal_missing=[],

        # Recovery
        recovery_options=[],
        recovery_strategy=None,

        # Events
        pending_events=[],
    )


def get_state_summary(state: StudyPlanState) -> str:
    """Get a text summary of current state for LLM context.

    This mirrors WorkingMemory.get_summary() from core/state.py.
    """
    parts = [
        "=== Current Progress ===",
        f"Run ID: {state.get('run_id', 'N/A')[:8]}...",
        f"Iterations: {state.get('iteration_count', 0)}",
        "",
        "--- Hypothesis ---",
    ]

    hypothesis = state.get("original_hypothesis", "")
    if len(hypothesis) > 100:
        parts.append(f"Original: {hypothesis[:100]}...")
    else:
        parts.append(f"Original: {hypothesis}")

    structured = state.get("structured_hypothesis")
    parts.append(f"Parsed: {'Yes' if structured else 'No'}")

    if structured:
        parts.append(f"Confidence: {state.get('hypothesis_confidence', 0):.0%}")
        parts.append("")
        parts.append("Structured Hypothesis:")
        parts.append(f"  IV: {structured.get('iv', 'N/A')}")
        parts.append(f"  DV: {structured.get('dv', 'N/A')}")
        parts.append(f"  Mechanism: {structured.get('mechanism', 'N/A')}")
        if structured.get("mediators"):
            parts.append(f"  Mediators: {structured.get('mediators')}")
        if structured.get("moderators"):
            parts.append(f"  Moderators: {structured.get('moderators')}")

    test_questions = state.get("test_questions", [])
    answered = state.get("answered_questions", [])
    parts.extend([
        "",
        "--- Research ---",
        f"Test Questions: {len(test_questions)} generated, {len(answered)} addressed",
    ])

    if test_questions:
        parts.append("")
        parts.append("Available Test Questions:")
        for i, q in enumerate(test_questions[:5]):
            q_text = q.get("question", str(q)) if isinstance(q, dict) else str(q)
            q_cat = q.get("category", "unknown") if isinstance(q, dict) else "unknown"
            parts.append(f"  Q{i+1} [{q_cat}]: {q_text[:80]}...")

    parts.extend([
        "",
        f"Papers Retrieved: {len(state.get('retrieved_papers', []))}",
        f"Evidence Snippets: {len(state.get('evidence_snippets', []))}",
        f"Search Coverage: {state.get('search_coverage', 0):.0%}",
        f"Search Tiers Used: {state.get('search_tiers_used', []) or 'None'}",
        "",
        "--- Design ---",
        f"Experiments Designed: {len(state.get('experiments', []))}",
        f"Controls Defined: {sum(len(c) for c in state.get('controls', {}).values())}",
        f"Measurements: {len(state.get('measurements', []))}",
        "",
        "--- Validation ---",
    ])

    quality = state.get("quality_score", 0)
    if quality:
        parts.append(f"Quality Score: {quality:.0%}")
    else:
        parts.append("Not evaluated")
    parts.append(f"Critique Rounds: {len(state.get('critique_history', []))}")

    parts.extend([
        "",
        "--- Output ---",
        f"Plan A: {'Generated' if state.get('plan_a') else 'Not yet'}",
        f"Plan B: {'Generated' if state.get('plan_b') else 'Not yet'}",
    ])

    # Urgency warnings
    iteration = state.get("iteration_count", 0)
    if iteration >= 20 and not state.get("plan_a"):
        parts.extend([
            "",
            "WARNING: Iteration 20+ reached without Plan A!",
            "   -> Call synthesize_plan NOW with available experiments",
        ])
    elif iteration >= 25 and not state.get("plan_b") and state.get("plan_a"):
        parts.extend([
            "",
            "WARNING: Iteration 25+ reached without Plan B!",
            "   -> Call generate_plan_b NOW",
        ])

    return "\n".join(parts)


def should_abort(state: StudyPlanState, max_consecutive: int = 5, max_same_error: int = 3) -> bool:
    """Check if agent should abort due to repeated failures.

    Args:
        state: Current state
        max_consecutive: Max consecutive failures before abort
        max_same_error: Max times same error can repeat before abort

    Returns:
        True if agent should abort
    """
    if state.get("critical_error"):
        return True
    if state.get("consecutive_failures", 0) >= max_consecutive:
        return True
    if state.get("same_error_count", 0) >= max_same_error:
        return True
    return False


def get_abort_reason(state: StudyPlanState) -> str | None:
    """Get the reason why agent should abort."""
    if critical := state.get("critical_error"):
        return f"Critical error: {critical}"
    if state.get("consecutive_failures", 0) >= 5:
        return f"Too many consecutive failures ({state.get('consecutive_failures')})"
    if state.get("same_error_count", 0) >= 3:
        return f"Same error repeated {state.get('same_error_count')} times: {state.get('last_error')}"
    return None
