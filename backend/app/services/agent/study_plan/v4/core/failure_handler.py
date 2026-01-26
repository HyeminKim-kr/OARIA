"""Failure handler component for v4 agent.

The FailureHandler is responsible for:
1. Classifying failure types
2. Selecting recovery strategies
3. Planning recovery actions
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.core.types import Action, RecoveryPlan
from app.services.agent.study_plan.v4.core.state import (
    WorkingMemory,
    ExecutionHistory,
)
from app.services.agent.study_plan.v4.prompts.recovery import RECOVERY_STRATEGY_PROMPT

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class FailureType:
    """Known failure types and their characteristics."""

    SEARCH_NO_RESULTS = "search_no_results"
    LOW_COVERAGE = "low_coverage"
    VALIDATION_FAILED = "validation_failed"
    QUALITY_LOW = "quality_low"
    TOOL_ERROR = "tool_error"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

    # Critical errors (복구 불가)
    API_KEY_MISSING = "api_key_missing"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SERVICE_UNAVAILABLE = "service_unavailable"

    # Critical 에러 목록
    CRITICAL_TYPES = {
        API_KEY_MISSING,
        AUTHENTICATION_FAILED,
        SERVICE_UNAVAILABLE,
    }


# Critical 에러 패턴 (에러 메시지에서 감지)
CRITICAL_ERROR_PATTERNS = [
    # API 키 관련
    ("api key", FailureType.API_KEY_MISSING),
    ("api_key", FailureType.API_KEY_MISSING),
    ("apikey", FailureType.API_KEY_MISSING),
    ("missing key", FailureType.API_KEY_MISSING),
    ("invalid key", FailureType.API_KEY_MISSING),
    ("no api key", FailureType.API_KEY_MISSING),
    ("tavily_api_key", FailureType.API_KEY_MISSING),
    ("openai_api_key", FailureType.API_KEY_MISSING),

    # 인증 관련
    ("unauthorized", FailureType.AUTHENTICATION_FAILED),
    ("authentication failed", FailureType.AUTHENTICATION_FAILED),
    ("401", FailureType.AUTHENTICATION_FAILED),
    ("403 forbidden", FailureType.AUTHENTICATION_FAILED),
    ("access denied", FailureType.AUTHENTICATION_FAILED),

    # Rate limit
    ("rate limit", FailureType.RATE_LIMIT_EXCEEDED),
    ("too many requests", FailureType.RATE_LIMIT_EXCEEDED),
    ("429", FailureType.RATE_LIMIT_EXCEEDED),
    ("quota exceeded", FailureType.RATE_LIMIT_EXCEEDED),

    # 서비스 불가
    ("service unavailable", FailureType.SERVICE_UNAVAILABLE),
    ("503", FailureType.SERVICE_UNAVAILABLE),
    ("502 bad gateway", FailureType.SERVICE_UNAVAILABLE),
]


@dataclass
class FailureContext:
    """Context about a failure for recovery planning."""

    failure_type: str
    error_message: str
    failed_action: str
    failed_input: dict
    attempt_count: int = 1


class FailureHandler:
    """Handles failures and plans recovery.

    Uses a combination of rule-based strategies and
    LLM-assisted decision making for complex cases.
    """

    # Recovery strategies for each failure type
    FAILURE_STRATEGIES: dict[str, list[str]] = {
        FailureType.SEARCH_NO_RESULTS: [
            "broaden_query",
            "try_different_tier",
            "ask_user_keywords",
        ],
        FailureType.LOW_COVERAGE: [
            "expand_search",
            "relax_constraints",
            "decompose_further",
        ],
        FailureType.VALIDATION_FAILED: [
            "redesign",
            "add_controls",
            "revise_hypothesis",
        ],
        FailureType.QUALITY_LOW: [
            "iterate_critique",
            "seek_more_evidence",
            "simplify_design",
        ],
        FailureType.TOOL_ERROR: [
            "retry_with_different_params",
            "try_alternative_tool",
            "ask_user",
        ],
        FailureType.PARSE_ERROR: [
            "simplify_input",
            "ask_user_clarification",
        ],
        FailureType.TIMEOUT: [
            "retry",
            "use_cached_result",
            "skip_optional",
        ],
        FailureType.UNKNOWN: [
            "ask_user",
        ],
    }

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        max_recovery_attempts: int = 3,
    ):
        """Initialize failure handler.

        Args:
            llm: Optional LLM for complex recovery decisions
            max_recovery_attempts: Max attempts before giving up
        """
        self.llm = llm
        self.max_recovery_attempts = max_recovery_attempts

    def classify_failure(self, error: str, action: str) -> str:
        """Classify the type of failure based on error message and action.

        Args:
            error: Error message
            action: The action that failed

        Returns:
            FailureType constant
        """
        error_lower = error.lower()

        # 1. Critical 에러 먼저 체크 (복구 불가)
        for pattern, failure_type in CRITICAL_ERROR_PATTERNS:
            if pattern in error_lower:
                return failure_type

        # 2. 일반 에러 체크
        if "no results" in error_lower or "not found" in error_lower:
            return FailureType.SEARCH_NO_RESULTS

        if "coverage" in error_lower or "insufficient" in error_lower:
            return FailureType.LOW_COVERAGE

        if "validation" in error_lower or "invalid" in error_lower:
            return FailureType.VALIDATION_FAILED

        if "quality" in error_lower or "score" in error_lower:
            return FailureType.QUALITY_LOW

        if "timeout" in error_lower or "timed out" in error_lower:
            return FailureType.TIMEOUT

        if "parse" in error_lower or "json" in error_lower:
            return FailureType.PARSE_ERROR

        if "error" in error_lower or "failed" in error_lower:
            return FailureType.TOOL_ERROR

        return FailureType.UNKNOWN

    def is_critical(self, failure_type: str) -> bool:
        """Check if the failure type is critical (unrecoverable).

        Args:
            failure_type: The classified failure type

        Returns:
            True if the failure is critical
        """
        return failure_type in FailureType.CRITICAL_TYPES

    async def handle(
        self,
        context: FailureContext,
        state: WorkingMemory,
        history: ExecutionHistory,
    ) -> RecoveryPlan:
        """Create a recovery plan for the failure.

        Args:
            context: Information about the failure
            state: Current working memory
            history: Execution history

        Returns:
            RecoveryPlan with strategy and actions
        """
        logger.info(
            f"Handling failure: {context.failure_type}, "
            f"attempt {context.attempt_count}/{self.max_recovery_attempts}"
        )

        # Check if max attempts exceeded
        if context.attempt_count >= self.max_recovery_attempts:
            return self._create_user_intervention_plan(context)

        # Get available strategies
        strategies = self.FAILURE_STRATEGIES.get(
            context.failure_type, [FailureType.UNKNOWN]
        )

        # Filter out already tried strategies
        tried = {s.action for s in history.steps if not s.success}
        available = [s for s in strategies if s not in tried]

        if not available:
            return self._create_user_intervention_plan(context)

        # For complex cases, use LLM if available
        if self.llm and len(available) > 1:
            return await self._llm_select_strategy(
                context, state, history, available
            )

        # Otherwise, use first available strategy
        strategy = available[0]
        return self._create_recovery_plan(strategy, context, state)

    def _create_recovery_plan(
        self,
        strategy: str,
        context: FailureContext,
        state: WorkingMemory,
    ) -> RecoveryPlan:
        """Create a recovery plan for a specific strategy."""
        actions = self._plan_recovery_actions(strategy, context, state)

        return RecoveryPlan(
            strategy=strategy,
            next_actions=actions,
            message=f"Attempting recovery with strategy: {strategy}",
        )

    def _plan_recovery_actions(
        self,
        strategy: str,
        context: FailureContext,
        state: WorkingMemory,
    ) -> list[Action]:
        """Plan specific actions for a recovery strategy."""
        actions = []

        if strategy == "broaden_query":
            # Broaden search query
            actions.append(
                Action(
                    name="search_rag",
                    input={
                        "query": self._broaden_query(
                            context.failed_input.get("query", "")
                        ),
                        "top_k": 20,
                    },
                )
            )

        elif strategy == "try_different_tier":
            # Try next search tier
            current_tier = max(state.search_tiers_used) if state.search_tiers_used else 1
            if current_tier < 3:
                next_tool = {1: "search_epmc", 2: "search_web"}.get(
                    current_tier, "search_web"
                )
                actions.append(
                    Action(
                        name=next_tool,
                        input={"query": context.failed_input.get("query", "")},
                    )
                )

        elif strategy == "add_controls":
            # Add missing controls to experiments
            for exp in state.experiments:
                exp_id = exp.get("id", str(hash(str(exp))))
                actions.append(
                    Action(
                        name="design_controls",
                        input={"experiment": exp},
                    )
                )

        elif strategy == "redesign":
            # Redesign experiments
            if state.critique_history:
                last_critique = state.critique_history[-1]
                actions.append(
                    Action(
                        name="design_experiment",
                        input={
                            "question": state.test_questions[0] if state.test_questions else {},
                            "evidence": state.evidence_snippets[:5],
                            "constraints": state.constraints,
                            "feedback": last_critique.get("suggestions", []),
                        },
                    )
                )

        elif strategy == "iterate_critique":
            # Run another round of critique
            actions.append(
                Action(
                    name="critique_design",
                    input={
                        "design": {
                            "experiments": state.experiments,
                            "controls": state.controls,
                            "measurements": state.measurements,
                        }
                    },
                )
            )

        elif strategy == "ask_user":
            actions.append(
                Action(
                    name="ask_user",
                    input={
                        "question": f"The agent encountered an issue: {context.error_message}. How should we proceed?",
                        "options": [
                            "Retry with simpler approach",
                            "Skip this step",
                            "Provide additional input",
                        ],
                    },
                )
            )

        return actions

    def _broaden_query(self, query: str) -> str:
        """Broaden a search query by removing specific terms."""
        # Simple heuristic: take first few words
        words = query.split()
        if len(words) > 5:
            return " ".join(words[:5])
        return query

    def _create_user_intervention_plan(
        self,
        context: FailureContext,
    ) -> RecoveryPlan:
        """Create a plan that requests user intervention."""
        return RecoveryPlan(
            strategy="ask_user",
            message=f"Automatic recovery failed after {context.attempt_count} attempts. User input required.",
            options=[
                "Provide additional guidance",
                "Skip this part and continue",
                "Cancel the operation",
            ],
            next_actions=[
                Action(
                    name="ask_user",
                    input={
                        "question": f"The agent could not recover from: {context.error_message}",
                        "options": [
                            "Provide additional guidance",
                            "Skip this part and continue",
                            "Cancel the operation",
                        ],
                    },
                )
            ],
        )

    async def _llm_select_strategy(
        self,
        context: FailureContext,
        state: WorkingMemory,
        history: ExecutionHistory,
        available_strategies: list[str],
    ) -> RecoveryPlan:
        """Use LLM to select best recovery strategy."""
        if not self.llm:
            # Fallback to first strategy
            return self._create_recovery_plan(
                available_strategies[0], context, state
            )

        tried_strategies = [
            s.action for s in history.steps if not s.success
        ]

        prompt = RECOVERY_STRATEGY_PROMPT.format(
            failure_type=context.failure_type,
            error_details=context.error_message,
            state_summary=state.get_summary(),
            available_strategies=", ".join(available_strategies),
            tried_strategies=", ".join(tried_strategies) if tried_strategies else "None",
        )

        try:
            response = await self.llm.ainvoke(prompt)
            # Parse response to get strategy
            import json
            import re

            json_match = re.search(r"\{[^}]+\}", response.content)
            if json_match:
                parsed = json.loads(json_match.group())
                strategy = parsed.get("chosen_strategy", available_strategies[0])
                if strategy in available_strategies:
                    return self._create_recovery_plan(strategy, context, state)

        except Exception as e:
            logger.warning(f"LLM strategy selection failed: {e}")

        # Fallback
        return self._create_recovery_plan(available_strategies[0], context, state)
