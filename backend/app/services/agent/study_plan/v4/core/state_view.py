"""Read-only view over LangGraph state.

StateView provides a read-only interface to access LangGraph state fields
without needing to copy data to a separate WorkingMemory object.

This eliminates the dual state management (WorkingMemory + LangGraph State)
problem by providing a single, consistent way to access state data.
"""

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.agent.study_plan.v4.langgraph.state import StudyPlanState


class StateView:
    """Read-only view of LangGraph state.

    Provides the same interface as WorkingMemory but without copying data.
    All access is through properties that read directly from the underlying state.

    Usage:
        state_view = StateView(langgraph_state)
        experiments = state_view.experiments  # Returns [] if not set
        hypothesis = state_view.structured_hypothesis  # Returns None if not set
    """

    __slots__ = ("_state",)

    def __init__(self, state: "StudyPlanState"):
        """Initialize with a LangGraph state.

        Args:
            state: The LangGraph StudyPlanState TypedDict
        """
        object.__setattr__(self, "_state", state)

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent attribute modification (read-only)."""
        raise AttributeError(
            f"StateView is read-only. Cannot set '{name}'. "
            "State updates should be returned from nodes."
        )

    def __delattr__(self, name: str) -> None:
        """Prevent attribute deletion (read-only)."""
        raise AttributeError(
            f"StateView is read-only. Cannot delete '{name}'."
        )

    # =========================================================================
    # Identification
    # =========================================================================

    @property
    def run_id(self) -> str:
        return self._state.get("run_id", "")

    @property
    def started_at(self) -> str:
        return self._state.get("started_at", "")

    # =========================================================================
    # Goal and Input
    # =========================================================================

    @property
    def goal(self) -> str:
        return self._state.get("goal", "")

    @property
    def original_hypothesis(self) -> str:
        return self._state.get("original_hypothesis", "")

    @property
    def research_context(self) -> str | None:
        return self._state.get("research_context")

    @property
    def constraints(self) -> list[str]:
        return self._state.get("constraints") or []

    @property
    def preferred_experiment_types(self) -> list[str]:
        return self._state.get("preferred_experiment_types") or []

    # =========================================================================
    # Parsed Hypothesis
    # =========================================================================

    @property
    def structured_hypothesis(self) -> dict[str, Any] | None:
        return self._state.get("structured_hypothesis")

    @property
    def hypothesis_confidence(self) -> float:
        return self._state.get("hypothesis_confidence", 0.0)

    # =========================================================================
    # Test Questions
    # =========================================================================

    @property
    def test_questions(self) -> list[dict[str, Any]]:
        return self._state.get("test_questions") or []

    @property
    def answered_questions(self) -> set[str]:
        """Return answered_questions as a set for compatibility."""
        answered = self._state.get("answered_questions") or []
        return set(answered)

    # =========================================================================
    # Search Results
    # =========================================================================

    @property
    def retrieved_papers(self) -> list[dict[str, Any]]:
        return self._state.get("retrieved_papers") or []

    @property
    def evidence_snippets(self) -> list[dict[str, Any]]:
        return self._state.get("evidence_snippets") or []

    @property
    def search_coverage(self) -> float:
        return self._state.get("search_coverage", 0.0)

    @property
    def search_tiers_used(self) -> list[int]:
        return self._state.get("search_tiers_used") or []

    # =========================================================================
    # Design Results
    # =========================================================================

    @property
    def experiments(self) -> list[dict[str, Any]]:
        return self._state.get("experiments") or []

    @property
    def controls(self) -> dict[str, list[dict[str, Any]]]:
        return self._state.get("controls") or {}

    @property
    def measurements(self) -> list[dict[str, Any]]:
        return self._state.get("measurements") or []

    # =========================================================================
    # Validation Results
    # =========================================================================

    @property
    def validation_results(self) -> list[dict[str, Any]]:
        return self._state.get("validation_results") or []

    @property
    def quality_score(self) -> float:
        return self._state.get("quality_score", 0.0)

    @property
    def critique_history(self) -> list[dict[str, Any]]:
        return self._state.get("critique_history") or []

    # =========================================================================
    # Output
    # =========================================================================

    @property
    def plan_a(self) -> str | None:
        return self._state.get("plan_a")

    @property
    def plan_b(self) -> str | None:
        return self._state.get("plan_b")

    @property
    def executive_summary(self) -> str | None:
        return self._state.get("executive_summary")

    # =========================================================================
    # Execution Control
    # =========================================================================

    @property
    def iteration_count(self) -> int:
        return self._state.get("iteration_count", 0)

    @property
    def max_iterations(self) -> int:
        return self._state.get("max_iterations", 30)

    @property
    def total_cost(self) -> float:
        return self._state.get("total_cost", 0.0)

    # =========================================================================
    # Token Tracking
    # =========================================================================

    @property
    def cumulative_tokens(self) -> dict[str, int]:
        return self._state.get("cumulative_tokens") or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    # =========================================================================
    # Failure Tracking
    # =========================================================================

    @property
    def failed_actions(self) -> dict[str, int]:
        return self._state.get("failed_actions") or {}

    @property
    def consecutive_failures(self) -> int:
        return self._state.get("consecutive_failures", 0)

    @property
    def last_error(self) -> str | None:
        return self._state.get("last_error")

    @property
    def same_error_count(self) -> int:
        return self._state.get("same_error_count", 0)

    @property
    def critical_error(self) -> str | None:
        return self._state.get("critical_error")

    # =========================================================================
    # Goal Status
    # =========================================================================

    @property
    def goal_achieved(self) -> bool:
        return self._state.get("goal_achieved", False)

    @property
    def goal_details(self) -> dict[str, bool]:
        return self._state.get("goal_details") or {}

    @property
    def goal_missing(self) -> list[str]:
        return self._state.get("goal_missing") or []

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_hypothesis_variables(self) -> set[str]:
        """Extract all variables from structured hypothesis.

        Returns:
            Set of variable names (IV, DV, mediators, moderators)
        """
        if not self.structured_hypothesis:
            return set()

        variables = set()
        hyp = self.structured_hypothesis

        if iv := hyp.get("iv"):
            variables.add(iv)
        if dv := hyp.get("dv"):
            variables.add(dv)
        if mediators := hyp.get("mediators"):
            variables.update(mediators)
        if moderators := hyp.get("moderators"):
            variables.update(moderators)

        return variables

    def get_summary(self) -> str:
        """Get current state summary for LLM context.

        This replicates WorkingMemory.get_summary() functionality.
        """
        # Import here to avoid circular import
        from app.services.agent.study_plan.v4.langgraph.state import get_state_summary
        return get_state_summary(self._state)

    def should_abort(self, max_consecutive: int = 5, max_same_error: int = 3) -> bool:
        """Check if agent should abort due to repeated failures.

        Args:
            max_consecutive: Max consecutive failures before abort
            max_same_error: Max times same error can repeat before abort

        Returns:
            True if agent should abort
        """
        if self.critical_error:
            return True
        if self.consecutive_failures >= max_consecutive:
            return True
        if self.same_error_count >= max_same_error:
            return True
        return False

    def get_abort_reason(self) -> str | None:
        """Get the reason why agent should abort."""
        if critical := self.critical_error:
            return f"Critical error: {critical}"
        if self.consecutive_failures >= 5:
            return f"Too many consecutive failures ({self.consecutive_failures})"
        if self.same_error_count >= 3:
            return f"Same error repeated {self.same_error_count} times: {self.last_error}"
        return None

    def should_avoid_action(self, action: str) -> bool:
        """Check if action has failed too many times (>= 2)."""
        return self.failed_actions.get(action, 0) >= 2

    # =========================================================================
    # Raw State Access (for debugging)
    # =========================================================================

    def get_raw_state(self) -> "StudyPlanState":
        """Get the underlying raw state (for debugging only).

        Warning: This bypasses the read-only protection. Do not modify
        the returned state directly - always return updates from nodes.
        """
        return self._state

    def __repr__(self) -> str:
        return (
            f"<StateView run_id={self.run_id[:8]}... "
            f"iter={self.iteration_count} "
            f"exp={len(self.experiments)} "
            f"papers={len(self.retrieved_papers)}>"
        )
