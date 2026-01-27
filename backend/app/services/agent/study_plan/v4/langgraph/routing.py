"""Conditional routing functions for LangGraph.

These functions determine the next node based on current state.
They replace the conditional logic in core/loop.py.
"""

from typing import Literal

from app.services.agent.study_plan.v4.langgraph.state import (
    StudyPlanState,
    should_abort,
)


# ============================================================================
# Node Names
# ============================================================================

INITIALIZE = "initialize"
REASON = "reason"
EXECUTE = "execute"
OBSERVE = "observe"
CHECK_GOAL = "check_goal"
FINALIZE = "finalize"
END = "__end__"


# ============================================================================
# Routing Functions
# ============================================================================

def route_after_observe(state: StudyPlanState) -> Literal["check_goal", "finalize"]:
    """Route after observation based on success/failure.

    Called after the observe node to determine next step.

    Args:
        state: Current state

    Returns:
        Next node name: "check_goal" or "finalize"
    """
    # Critical error -> finalize immediately
    if state.get("critical_error"):
        return FINALIZE

    # Check abort conditions (max consecutive failures, same error repeated)
    if should_abort(state):
        return FINALIZE

    # Continue to goal check
    return CHECK_GOAL


def route_after_goal_check(state: StudyPlanState) -> Literal["reason", "finalize"]:
    """Route after goal check.

    Called after the check_goal node to determine if we continue or finish.

    Args:
        state: Current state

    Returns:
        Next node name: "reason" (continue loop) or "finalize" (done)
    """
    # Goal achieved -> finalize
    if state.get("goal_achieved"):
        return FINALIZE

    # FINISH action explicitly called -> finalize
    if state.get("current_action") == "FINISH":
        return FINALIZE

    # Max iterations reached -> finalize
    iteration = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations", 30)
    if iteration >= max_iter:
        return FINALIZE

    # Continue reasoning
    return REASON


def route_after_execute(state: StudyPlanState) -> Literal["observe"]:
    """Route after execution.

    Currently always goes to observe, but can be extended for
    special handling of certain actions.

    Args:
        state: Current state

    Returns:
        Next node name: always "observe"
    """
    return OBSERVE


def should_force_synthesize(state: StudyPlanState) -> bool:
    """Check if we should force synthesize_plan.

    Called when iteration count is high but plan_a is missing.

    Args:
        state: Current state

    Returns:
        True if should force synthesize
    """
    iteration = state.get("iteration_count", 0)
    has_experiments = len(state.get("experiments", [])) > 0
    has_plan_a = state.get("plan_a") is not None

    # Force synthesize at iteration 20+ if we have experiments but no plan
    return iteration >= 20 and has_experiments and not has_plan_a


def should_force_plan_b(state: StudyPlanState) -> bool:
    """Check if we should force generate_plan_b.

    Called when plan_a exists but plan_b is missing at high iteration.

    Args:
        state: Current state

    Returns:
        True if should force plan_b generation
    """
    iteration = state.get("iteration_count", 0)
    has_plan_a = state.get("plan_a") is not None
    has_plan_b = state.get("plan_b") is not None

    # Force plan_b at iteration 25+ if we have plan_a
    return iteration >= 25 and has_plan_a and not has_plan_b


def validate_finish_allowed(state: StudyPlanState) -> tuple[bool, str | None, str | None]:
    """Validate if FINISH action is allowed.

    Checks if all required steps have been completed.

    Args:
        state: Current state

    Returns:
        Tuple of (is_blocked, reason, suggested_action)
        - is_blocked: True if FINISH should be blocked
        - reason: Why FINISH is blocked
        - suggested_action: What action to take instead
    """
    # Check required steps in order
    if not state.get("structured_hypothesis"):
        return True, "Hypothesis not yet parsed", "parse_hypothesis"

    if len(state.get("test_questions", [])) < 1:
        return True, "No test questions generated", "decompose_questions"

    if len(state.get("experiments", [])) < 1:
        return True, "No experiments designed", "design_experiment"

    if not state.get("plan_a"):
        return True, "Plan A not yet synthesized", "synthesize_plan"

    if not state.get("plan_b"):
        return True, "Plan B not yet generated", "generate_plan_b"

    # All requirements met, FINISH is allowed
    return False, None, None


def get_blocked_actions(state: StudyPlanState) -> set[str]:
    """Get actions that should be avoided due to repeated failures.

    Args:
        state: Current state

    Returns:
        Set of action names to avoid
    """
    failed = state.get("failed_actions", {})
    return {action for action, count in failed.items() if count >= 2}


def detect_loop(state: StudyPlanState, window: int = 4) -> bool:
    """Detect if agent is stuck in a loop.

    Checks if the same action sequence repeats.

    Args:
        state: Current state
        window: Window size for loop detection

    Returns:
        True if loop detected
    """
    history = state.get("execution_history", [])
    if len(history) < window * 2:
        return False

    recent_actions = [h.get("action", "") for h in history[-window:]]
    previous_actions = [h.get("action", "") for h in history[-window * 2:-window]]

    return recent_actions == previous_actions


def get_recovery_options(error: str, action: str) -> list[dict]:
    """Generate recovery options based on error type and action.

    Args:
        error: Error message
        action: Action that failed

    Returns:
        List of recovery option dicts
    """
    options = []

    # Search-related failures
    if "search" in action.lower() or "rag" in action.lower():
        options.append({
            "id": "retry_different_keywords",
            "label": "다른 키워드로 재시도",
            "description": "검색 쿼리를 확장하여 다시 시도합니다",
            "risk_level": "low",
            "estimated_time": "30초",
        })
        options.append({
            "id": "external_search",
            "label": "외부 DB 검색",
            "description": "EPMC 또는 PubMed에서 직접 검색합니다",
            "risk_level": "medium",
            "estimated_time": "1분",
        })

    # Design-related failures
    if "design" in action.lower() or "experiment" in action.lower():
        options.append({
            "id": "simplify_design",
            "label": "설계 단순화",
            "description": "더 단순한 실험 설계로 재시도합니다",
            "risk_level": "low",
            "estimated_time": "30초",
        })
        options.append({
            "id": "use_template",
            "label": "표준 템플릿 사용",
            "description": "검증된 표준 실험 템플릿을 적용합니다",
            "risk_level": "low",
            "estimated_time": "20초",
        })

    # Validation failures
    if "validate" in action.lower() or "critique" in action.lower():
        options.append({
            "id": "relax_criteria",
            "label": "기준 완화",
            "description": "검증 기준을 완화하여 재평가합니다",
            "risk_level": "medium",
            "estimated_time": "20초",
        })

    # Synthesis failures
    if "synthesize" in action.lower() or "plan" in action.lower():
        options.append({
            "id": "partial_synthesis",
            "label": "부분 합성",
            "description": "사용 가능한 데이터로 부분적인 계획을 생성합니다",
            "risk_level": "medium",
            "estimated_time": "1분",
        })

    # Universal skip option
    options.append({
        "id": "skip",
        "label": "이 단계 건너뛰기",
        "description": "현재 단계를 건너뛰고 다음으로 진행합니다",
        "risk_level": "high",
        "estimated_time": "즉시",
    })

    return options


# ============================================================================
# Event Types (for compatibility with existing streaming)
# ============================================================================

class AgentLoopEvent:
    """Event types emitted during agent execution.

    Mirrors the events from core/loop.py for frontend compatibility.
    """

    STARTED = "started"
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVATION = "observation"
    RECOVERY = "recovery"
    GOAL_CHECK = "goal_check"
    COMPLETED = "completed"
    ERROR = "error"
