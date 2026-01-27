"""State management for v4 agent.

Includes:
- WorkingMemory: Current execution state
- ExecutionHistory: Trace of actions taken
- ExecutionStep: Single step record
- CumulativeTokens: Token usage tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


# ============================================================================
# Token Tracking
# ============================================================================

@dataclass
class CumulativeTokens:
    """Cumulative token usage tracking for LLM calls."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, usage: dict[str, int] | None) -> None:
        """Add token usage from a single LLM call.

        Args:
            usage: Dict with prompt_tokens, completion_tokens, total_tokens
        """
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

    def estimate_cost(self, model: str = "gpt-4") -> float:
        """Estimate cost based on model pricing.

        Args:
            model: Model name for pricing lookup

        Returns:
            Estimated cost in USD
        """
        # Pricing per 1K tokens (approximate)
        pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-4o": {"prompt": 0.005, "completion": 0.015},
            "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
        }

        rates = pricing.get(model, pricing["gpt-4"])
        prompt_cost = (self.prompt_tokens / 1000) * rates["prompt"]
        completion_cost = (self.completion_tokens / 1000) * rates["completion"]

        return prompt_cost + completion_cost


# ============================================================================
# Execution Step
# ============================================================================


@dataclass
class ExecutionStep:
    """Record of a single execution step."""

    step_number: int
    timestamp: datetime
    thought: str
    action: str
    action_input: dict[str, Any]
    observation: dict[str, Any]
    success: bool
    error: str | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step_number": self.step_number,
            "timestamp": self.timestamp.isoformat(),
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "success": self.success,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class ExecutionHistory:
    """History of all execution steps in current run."""

    def __init__(self):
        self.steps: list[ExecutionStep] = []
        self.failed_actions: dict[str, int] = {}  # action -> failure count
        self._action_sequence: list[str] = []  # for loop detection
        self._consecutive_failures: int = 0  # 연속 실패 카운터
        self._last_error: str | None = None  # 마지막 에러 메시지
        self._same_error_count: int = 0  # 동일 에러 반복 카운터
        self._critical_error: str | None = None  # Critical 에러 (복구 불가)

    def add_step(self, step: ExecutionStep) -> None:
        """Add a new step to history."""
        self.steps.append(step)
        self._action_sequence.append(step.action)

        if not step.success:
            self.failed_actions[step.action] = (
                self.failed_actions.get(step.action, 0) + 1
            )
            self._consecutive_failures += 1

            # 동일 에러 추적
            if step.error and step.error == self._last_error:
                self._same_error_count += 1
            else:
                self._same_error_count = 1
                self._last_error = step.error
        else:
            # 성공 시 연속 실패 카운터 리셋
            self._consecutive_failures = 0
            self._same_error_count = 0
            self._last_error = None

    def set_critical_error(self, error: str) -> None:
        """Set a critical error that should stop execution."""
        self._critical_error = error

    def has_critical_error(self) -> bool:
        """Check if a critical error has occurred."""
        return self._critical_error is not None

    def get_critical_error(self) -> str | None:
        """Get the critical error message."""
        return self._critical_error

    def should_abort(self, max_consecutive: int = 5, max_same_error: int = 3) -> bool:
        """Check if agent should abort due to repeated failures.

        Args:
            max_consecutive: Max consecutive failures before abort
            max_same_error: Max times same error can repeat before abort

        Returns:
            True if agent should abort
        """
        if self._critical_error:
            return True
        if self._consecutive_failures >= max_consecutive:
            return True
        if self._same_error_count >= max_same_error:
            return True
        return False

    def get_abort_reason(self) -> str | None:
        """Get the reason why agent should abort."""
        if self._critical_error:
            return f"Critical error: {self._critical_error}"
        if self._consecutive_failures >= 5:
            return f"Too many consecutive failures ({self._consecutive_failures})"
        if self._same_error_count >= 3:
            return f"Same error repeated {self._same_error_count} times: {self._last_error}"
        return None

    def get_recent(self, n: int = 5) -> list[ExecutionStep]:
        """Get the n most recent steps."""
        return self.steps[-n:]

    def should_avoid(self, action: str) -> bool:
        """Check if action has failed too many times (>= 2)."""
        return self.failed_actions.get(action, 0) >= 2

    def detect_loop(self, window: int = 4) -> bool:
        """Detect if agent is stuck in a loop.

        Checks if the same action sequence repeats.
        """
        if len(self._action_sequence) < window * 2:
            return False

        recent = self._action_sequence[-window:]
        previous = self._action_sequence[-window * 2 : -window]
        return recent == previous

    def get_context_for_llm(self, n: int = 5) -> str:
        """Format recent steps for LLM context."""
        recent = self.get_recent(n)
        if not recent:
            return "No previous actions."

        lines = []
        for step in recent:
            status = "SUCCESS" if step.success else "FAILED"
            # Truncate thought for brevity
            thought_preview = (
                step.thought[:100] + "..." if len(step.thought) > 100 else step.thought
            )
            lines.append(f"[{status}] {step.action}: {thought_preview}")

        return "\n".join(lines)

    def get_successful_actions(self) -> list[str]:
        """Get list of successfully executed actions."""
        return [s.action for s in self.steps if s.success]

    def to_trace(self) -> list[dict[str, Any]]:
        """Convert entire history to serializable trace."""
        return [step.to_dict() for step in self.steps]


@dataclass
class WorkingMemory:
    """Working memory for current agent execution.

    Contains all intermediate state needed during plan generation.
    """

    # Run identification
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=datetime.utcnow)

    # Goal and input
    goal: str = ""
    original_hypothesis: str = ""
    research_context: str | None = None
    constraints: list[str] = field(default_factory=list)
    preferred_experiment_types: list[str] = field(default_factory=list)

    # Parsed hypothesis
    structured_hypothesis: dict[str, Any] | None = None
    hypothesis_confidence: float = 0.0

    # Test questions (NSPE decomposition)
    test_questions: list[dict[str, Any]] = field(default_factory=list)
    answered_questions: set[str] = field(default_factory=set)

    # Search results
    retrieved_papers: list[dict[str, Any]] = field(default_factory=list)
    evidence_snippets: list[dict[str, Any]] = field(default_factory=list)
    search_coverage: float = 0.0
    search_tiers_used: list[int] = field(default_factory=list)

    # Design results
    experiments: list[dict[str, Any]] = field(default_factory=list)
    controls: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    measurements: list[dict[str, Any]] = field(default_factory=list)

    # Validation results
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    quality_score: float = 0.0
    critique_history: list[dict[str, Any]] = field(default_factory=list)

    # Final output
    plan_a: str | None = None
    plan_b: str | None = None
    executive_summary: str | None = None

    # Metadata
    iteration_count: int = 0
    total_cost: float = 0.0
    user_questions: list[dict[str, Any]] = field(default_factory=list)

    # Token tracking
    cumulative_tokens: CumulativeTokens = field(default_factory=CumulativeTokens)

    def increment_iteration(self) -> None:
        """Increment iteration counter."""
        self.iteration_count += 1

    def add_cost(self, cost: float) -> None:
        """Add to total cost."""
        self.total_cost += cost

    def get_summary(self) -> str:
        """Get current state summary for LLM context."""
        parts = [
            "=== Current Progress ===",
            f"Run ID: {self.run_id[:8]}...",
            f"Iterations: {self.iteration_count}",
            "",
            "--- Hypothesis ---",
            f"Original: {self.original_hypothesis[:100]}..."
            if len(self.original_hypothesis) > 100
            else f"Original: {self.original_hypothesis}",
            f"Parsed: {'Yes' if self.structured_hypothesis else 'No'}",
        ]

        # Include structured hypothesis details if available (for tool parameter passing)
        if self.structured_hypothesis:
            parts.append(f"Confidence: {self.hypothesis_confidence:.0%}")
            parts.append("")
            parts.append("Structured Hypothesis (use this for decompose_questions):")
            parts.append(f"  IV: {self.structured_hypothesis.get('iv', 'N/A')}")
            parts.append(f"  DV: {self.structured_hypothesis.get('dv', 'N/A')}")
            parts.append(f"  Mechanism: {self.structured_hypothesis.get('mechanism', 'N/A')}")
            if self.structured_hypothesis.get('mediators'):
                parts.append(f"  Mediators: {self.structured_hypothesis.get('mediators')}")
            if self.structured_hypothesis.get('moderators'):
                parts.append(f"  Moderators: {self.structured_hypothesis.get('moderators')}")

        parts.extend([
            "",
            "--- Research ---",
            f"Test Questions: {len(self.test_questions)} generated, {len(self.answered_questions)} addressed",
        ])

        # Include test questions for design_experiment calls
        if self.test_questions:
            parts.append("")
            parts.append("Available Test Questions (use these for design_experiment):")
            for i, q in enumerate(self.test_questions[:5]):  # Show first 5
                q_text = q.get('question', str(q)) if isinstance(q, dict) else str(q)
                q_cat = q.get('category', 'unknown') if isinstance(q, dict) else 'unknown'
                parts.append(f"  Q{i+1} [{q_cat}]: {q_text[:80]}...")

        parts.extend([
            "",
            f"Papers Retrieved: {len(self.retrieved_papers)}",
            f"Evidence Snippets: {len(self.evidence_snippets)}",
            f"Search Coverage: {self.search_coverage:.0%}",
            f"Search Tiers Used: {self.search_tiers_used if self.search_tiers_used else 'None'}",
            "",
            "--- Design ---",
            f"Experiments Designed: {len(self.experiments)}",
            f"Controls Defined: {sum(len(c) for c in self.controls.values())}",
            f"Measurements: {len(self.measurements)}",
            "",
            "--- Validation ---",
            f"Quality Score: {self.quality_score:.0%}" if self.quality_score else "Not evaluated",
            f"Critique Rounds: {len(self.critique_history)}",
            "",
            "--- Output ---",
            f"Plan A: {'Generated' if self.plan_a else 'Not yet'}",
            f"Plan B: {'Generated' if self.plan_b else 'Not yet'}",
        ])

        # Add urgency warning for high iteration counts
        if self.iteration_count >= 20 and not self.plan_a:
            parts.append("")
            parts.append("⚠️ WARNING: Iteration 20+ reached without Plan A!")
            parts.append("   → Call synthesize_plan NOW with available experiments")
        elif self.iteration_count >= 25 and not self.plan_b and self.plan_a:
            parts.append("")
            parts.append("⚠️ WARNING: Iteration 25+ reached without Plan B!")
            parts.append("   → Call generate_plan_b NOW")

        return "\n".join(parts)

    def get_hypothesis_variables(self) -> set[str]:
        """Extract all variables from structured hypothesis."""
        if not self.structured_hypothesis:
            return set()

        variables = set()
        if iv := self.structured_hypothesis.get("iv"):
            variables.add(iv)
        if dv := self.structured_hypothesis.get("dv"):
            variables.add(dv)
        if mediators := self.structured_hypothesis.get("mediators"):
            variables.update(mediators)
        if moderators := self.structured_hypothesis.get("moderators"):
            variables.update(moderators)

        return variables

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "goal": self.goal,
            "original_hypothesis": self.original_hypothesis,
            "research_context": self.research_context,
            "constraints": self.constraints,
            "preferred_experiment_types": self.preferred_experiment_types,
            "structured_hypothesis": self.structured_hypothesis,
            "hypothesis_confidence": self.hypothesis_confidence,
            "test_questions": self.test_questions,
            "answered_questions": list(self.answered_questions),
            "retrieved_papers": self.retrieved_papers,
            "evidence_snippets": self.evidence_snippets,
            "search_coverage": self.search_coverage,
            "search_tiers_used": self.search_tiers_used,
            "experiments": self.experiments,
            "controls": self.controls,
            "measurements": self.measurements,
            "validation_results": self.validation_results,
            "quality_score": self.quality_score,
            "critique_history": self.critique_history,
            "plan_a": self.plan_a,
            "plan_b": self.plan_b,
            "executive_summary": self.executive_summary,
            "iteration_count": self.iteration_count,
            "total_cost": self.total_cost,
            "user_questions": self.user_questions,
            "cumulative_tokens": self.cumulative_tokens.to_dict(),
        }
