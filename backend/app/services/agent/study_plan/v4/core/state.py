"""State management for v4 agent.

Includes:
- ExecutionHistory: Trace of actions taken
- ExecutionStep: Single step record
- CumulativeTokens: Token usage tracking

Note: WorkingMemory has been replaced by StateView (see state_view.py)
which provides a read-only view over the LangGraph state without copying data.
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
