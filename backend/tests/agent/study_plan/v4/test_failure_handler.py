"""Tests for v4 failure handler - failure classification and recovery planning."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.agent.study_plan.v4.core.failure_handler import (
    FailureHandler,
    FailureType,
    FailureContext,
)
from app.services.agent.study_plan.v4.core.types import Action, RecoveryPlan
from app.services.agent.study_plan.v4.core.state import (
    WorkingMemory,
    ExecutionHistory,
    ExecutionStep,
)


# ─────────────────────────────────────────────────────────────
# FailureType Tests
# ─────────────────────────────────────────────────────────────


class TestFailureType:
    """Test FailureType constants."""

    def test_failure_types_are_strings(self):
        """Test that all failure types are strings."""
        assert isinstance(FailureType.SEARCH_NO_RESULTS, str)
        assert isinstance(FailureType.LOW_COVERAGE, str)
        assert isinstance(FailureType.VALIDATION_FAILED, str)
        assert isinstance(FailureType.QUALITY_LOW, str)
        assert isinstance(FailureType.TOOL_ERROR, str)
        assert isinstance(FailureType.PARSE_ERROR, str)
        assert isinstance(FailureType.TIMEOUT, str)
        assert isinstance(FailureType.UNKNOWN, str)

    def test_failure_types_are_unique(self):
        """Test that all failure types are unique."""
        types = [
            FailureType.SEARCH_NO_RESULTS,
            FailureType.LOW_COVERAGE,
            FailureType.VALIDATION_FAILED,
            FailureType.QUALITY_LOW,
            FailureType.TOOL_ERROR,
            FailureType.PARSE_ERROR,
            FailureType.TIMEOUT,
            FailureType.UNKNOWN,
        ]
        assert len(types) == len(set(types))


# ─────────────────────────────────────────────────────────────
# FailureContext Tests
# ─────────────────────────────────────────────────────────────


class TestFailureContext:
    """Test FailureContext dataclass."""

    def test_create_failure_context(self):
        """Test creating a failure context."""
        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results found for query",
            failed_action="search_rag",
            failed_input={"query": "test query"},
            attempt_count=1,
        )

        assert context.failure_type == FailureType.SEARCH_NO_RESULTS
        assert context.error_message == "No results found for query"
        assert context.failed_action == "search_rag"
        assert context.failed_input == {"query": "test query"}
        assert context.attempt_count == 1

    def test_default_attempt_count(self):
        """Test default attempt count is 1."""
        context = FailureContext(
            failure_type=FailureType.UNKNOWN,
            error_message="Error",
            failed_action="test",
            failed_input={},
        )

        assert context.attempt_count == 1


# ─────────────────────────────────────────────────────────────
# FailureHandler Initialization Tests
# ─────────────────────────────────────────────────────────────


class TestFailureHandlerInit:
    """Test FailureHandler initialization."""

    def test_init_without_llm(self):
        """Test initialization without LLM."""
        handler = FailureHandler()

        assert handler.llm is None
        assert handler.max_recovery_attempts == 3

    def test_init_with_llm(self, mock_llm):
        """Test initialization with LLM."""
        handler = FailureHandler(llm=mock_llm)

        assert handler.llm == mock_llm

    def test_init_with_custom_max_attempts(self):
        """Test initialization with custom max attempts."""
        handler = FailureHandler(max_recovery_attempts=5)

        assert handler.max_recovery_attempts == 5


# ─────────────────────────────────────────────────────────────
# classify_failure Tests
# ─────────────────────────────────────────────────────────────


class TestClassifyFailure:
    """Test classify_failure method."""

    def test_classify_no_results(self):
        """Test classifying 'no results' error."""
        handler = FailureHandler()

        result = handler.classify_failure("No results found", "search_rag")

        assert result == FailureType.SEARCH_NO_RESULTS

    def test_classify_not_found(self):
        """Test classifying 'not found' error."""
        handler = FailureHandler()

        result = handler.classify_failure("Paper not found in database", "search_epmc")

        assert result == FailureType.SEARCH_NO_RESULTS

    def test_classify_low_coverage(self):
        """Test classifying coverage-related error."""
        handler = FailureHandler()

        result = handler.classify_failure(
            "Coverage is insufficient for hypothesis", "validate_coverage"
        )

        assert result == FailureType.LOW_COVERAGE

    def test_classify_validation_failed(self):
        """Test classifying validation error."""
        handler = FailureHandler()

        result = handler.classify_failure(
            "Validation failed: missing controls", "validate_controls"
        )

        assert result == FailureType.VALIDATION_FAILED

    def test_classify_invalid_input(self):
        """Test classifying invalid input error."""
        handler = FailureHandler()

        result = handler.classify_failure(
            "Invalid experiment design", "design_experiment"
        )

        assert result == FailureType.VALIDATION_FAILED

    def test_classify_quality_low(self):
        """Test classifying quality-related error."""
        handler = FailureHandler()

        result = handler.classify_failure(
            "Quality score below threshold", "critique_design"
        )

        assert result == FailureType.QUALITY_LOW

    def test_classify_timeout(self):
        """Test classifying timeout error."""
        handler = FailureHandler()

        result = handler.classify_failure("Request timed out", "search_web")

        assert result == FailureType.TIMEOUT

    def test_classify_parse_error(self):
        """Test classifying parse error."""
        handler = FailureHandler()

        result = handler.classify_failure(
            "JSON parse error in response", "parse_hypothesis"
        )

        assert result == FailureType.PARSE_ERROR

    def test_classify_tool_error(self):
        """Test classifying generic tool error."""
        handler = FailureHandler()

        result = handler.classify_failure(
            "Tool error: connection failed", "search_epmc"
        )

        assert result == FailureType.TOOL_ERROR

    def test_classify_unknown(self):
        """Test classifying unknown error."""
        handler = FailureHandler()

        result = handler.classify_failure(
            "Something unexpected happened", "some_action"
        )

        assert result == FailureType.UNKNOWN


# ─────────────────────────────────────────────────────────────
# handle Tests
# ─────────────────────────────────────────────────────────────


class TestHandle:
    """Test handle method."""

    @pytest.mark.asyncio
    async def test_handle_returns_recovery_plan(self):
        """Test that handle returns a RecoveryPlan."""
        handler = FailureHandler()
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results found",
            failed_action="search_rag",
            failed_input={"query": "test"},
            attempt_count=1,
        )

        result = await handler.handle(context, state, history)

        assert isinstance(result, RecoveryPlan)
        assert result.strategy is not None
        assert result.message is not None

    @pytest.mark.asyncio
    async def test_handle_returns_user_intervention_when_max_attempts_exceeded(self):
        """Test that handle returns user intervention plan when max attempts exceeded."""
        handler = FailureHandler(max_recovery_attempts=2)
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.TOOL_ERROR,
            error_message="Persistent error",
            failed_action="search_rag",
            failed_input={},
            attempt_count=3,  # Exceeds max of 2
        )

        result = await handler.handle(context, state, history)

        assert result.strategy == "ask_user"
        assert "User input required" in result.message

    @pytest.mark.asyncio
    async def test_handle_selects_first_available_strategy(self):
        """Test that handle selects first available strategy without LLM."""
        handler = FailureHandler()  # No LLM
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results",
            failed_action="search_rag",
            failed_input={"query": "test"},
            attempt_count=1,
        )

        result = await handler.handle(context, state, history)

        # First strategy for SEARCH_NO_RESULTS is "broaden_query"
        assert result.strategy == "broaden_query"

    @pytest.mark.asyncio
    async def test_handle_filters_tried_strategies(self):
        """Test that handle filters out already tried strategies."""
        handler = FailureHandler()
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        # Add a failed step with first strategy
        step = ExecutionStep(
            step_number=1,
            timestamp=datetime.utcnow(),
            thought="Tried broaden_query",
            action="broaden_query",
            action_input={},
            observation={},
            success=False,
            error="Still no results",
        )
        history.add_step(step)

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results",
            failed_action="search_rag",
            failed_input={"query": "test"},
            attempt_count=2,
        )

        result = await handler.handle(context, state, history)

        # Should skip "broaden_query" and use next strategy
        assert result.strategy != "broaden_query"

    @pytest.mark.asyncio
    async def test_handle_with_llm(self, mock_llm):
        """Test that handle uses LLM when available."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.content = '{"chosen_strategy": "try_different_tier"}'
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        handler = FailureHandler(llm=mock_llm)
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results",
            failed_action="search_rag",
            failed_input={"query": "test"},
            attempt_count=1,
        )

        result = await handler.handle(context, state, history)

        # LLM was called
        mock_llm.ainvoke.assert_called_once()
        assert result.strategy == "try_different_tier"


# ─────────────────────────────────────────────────────────────
# Recovery Action Planning Tests
# ─────────────────────────────────────────────────────────────


class TestRecoveryActionPlanning:
    """Test _plan_recovery_actions method."""

    @pytest.mark.asyncio
    async def test_broaden_query_action(self):
        """Test broaden_query strategy creates appropriate action."""
        handler = FailureHandler()
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results",
            failed_action="search_rag",
            failed_input={"query": "very specific long query with many terms"},
            attempt_count=1,
        )

        result = await handler.handle(context, state, history)

        assert len(result.next_actions) > 0
        assert result.next_actions[0].name == "search_rag"
        # Query should be broadened (shortened)
        assert len(result.next_actions[0].input["query"].split()) <= 5

    @pytest.mark.asyncio
    async def test_try_different_tier_action(self):
        """Test try_different_tier strategy creates appropriate action."""
        handler = FailureHandler()
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        state.search_tiers_used = [1]  # Already used tier 1 (RAG)
        history = ExecutionHistory()

        # Add a step to skip "broaden_query"
        step = ExecutionStep(
            step_number=1,
            timestamp=datetime.utcnow(),
            thought="Tried broaden",
            action="broaden_query",
            action_input={},
            observation={},
            success=False,
        )
        history.add_step(step)

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results",
            failed_action="search_rag",
            failed_input={"query": "test"},
            attempt_count=2,
        )

        result = await handler.handle(context, state, history)

        assert result.strategy == "try_different_tier"
        assert len(result.next_actions) > 0
        # Should upgrade to tier 2 (EPMC)
        assert result.next_actions[0].name == "search_epmc"

    @pytest.mark.asyncio
    async def test_add_controls_action(self):
        """Test add_controls strategy creates actions for experiments."""
        handler = FailureHandler()
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        state.experiments = [
            {"id": "EXP-001", "name": "Experiment 1"},
            {"id": "EXP-002", "name": "Experiment 2"},
        ]
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.VALIDATION_FAILED,
            error_message="Missing controls",
            failed_action="validate_controls",
            failed_input={},
            attempt_count=1,
        )

        # Skip to add_controls strategy by marking previous ones as tried
        for action in ["redesign"]:
            step = ExecutionStep(
                step_number=1,
                timestamp=datetime.utcnow(),
                thought="Tried",
                action=action,
                action_input={},
                observation={},
                success=False,
            )
            history.add_step(step)

        result = await handler.handle(context, state, history)

        assert result.strategy == "add_controls"
        # Should create action for each experiment
        assert len(result.next_actions) == 2
        assert all(a.name == "design_controls" for a in result.next_actions)

    @pytest.mark.asyncio
    async def test_ask_user_action(self):
        """Test ask_user strategy creates appropriate action."""
        handler = FailureHandler()
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.UNKNOWN,
            error_message="Something went wrong",
            failed_action="some_action",
            failed_input={},
            attempt_count=1,
        )

        result = await handler.handle(context, state, history)

        assert result.strategy == "ask_user"
        assert len(result.next_actions) > 0
        assert result.next_actions[0].name == "ask_user"
        assert "options" in result.next_actions[0].input


# ─────────────────────────────────────────────────────────────
# User Intervention Tests
# ─────────────────────────────────────────────────────────────


class TestUserIntervention:
    """Test user intervention plan creation."""

    @pytest.mark.asyncio
    async def test_user_intervention_plan_structure(self):
        """Test structure of user intervention plan."""
        handler = FailureHandler(max_recovery_attempts=1)
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.TOOL_ERROR,
            error_message="Persistent failure",
            failed_action="test",
            failed_input={},
            attempt_count=2,  # Exceeds max of 1
        )

        result = await handler.handle(context, state, history)

        assert result.strategy == "ask_user"
        assert "Automatic recovery failed" in result.message
        assert result.options is not None
        assert len(result.options) == 3  # 3 default options
        assert "Cancel the operation" in result.options

    @pytest.mark.asyncio
    async def test_user_intervention_includes_error_message(self):
        """Test that user intervention plan includes original error."""
        handler = FailureHandler(max_recovery_attempts=1)
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        error_msg = "Specific error: API rate limit exceeded"
        context = FailureContext(
            failure_type=FailureType.TOOL_ERROR,
            error_message=error_msg,
            failed_action="search_web",
            failed_input={},
            attempt_count=2,
        )

        result = await handler.handle(context, state, history)

        # Error should be included in the ask_user input
        assert result.next_actions[0].name == "ask_user"
        assert error_msg in result.next_actions[0].input["question"]


# ─────────────────────────────────────────────────────────────
# Strategy Configuration Tests
# ─────────────────────────────────────────────────────────────


class TestStrategyConfiguration:
    """Test failure strategy configuration."""

    def test_all_failure_types_have_strategies(self):
        """Test that all failure types have defined strategies."""
        failure_types = [
            FailureType.SEARCH_NO_RESULTS,
            FailureType.LOW_COVERAGE,
            FailureType.VALIDATION_FAILED,
            FailureType.QUALITY_LOW,
            FailureType.TOOL_ERROR,
            FailureType.PARSE_ERROR,
            FailureType.TIMEOUT,
            FailureType.UNKNOWN,
        ]

        for ft in failure_types:
            assert ft in FailureHandler.FAILURE_STRATEGIES
            assert len(FailureHandler.FAILURE_STRATEGIES[ft]) > 0

    def test_strategies_are_lists(self):
        """Test that all strategies are lists."""
        for strategies in FailureHandler.FAILURE_STRATEGIES.values():
            assert isinstance(strategies, list)
            assert all(isinstance(s, str) for s in strategies)


# ─────────────────────────────────────────────────────────────
# LLM Strategy Selection Tests
# ─────────────────────────────────────────────────────────────


class TestLLMStrategySelection:
    """Test LLM-assisted strategy selection."""

    @pytest.mark.asyncio
    async def test_llm_selection_with_valid_response(self, mock_llm):
        """Test LLM selection with valid JSON response."""
        mock_response = MagicMock()
        mock_response.content = 'Based on analysis: {"chosen_strategy": "try_different_tier"}'
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        handler = FailureHandler(llm=mock_llm)
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results",
            failed_action="search_rag",
            failed_input={},
            attempt_count=1,
        )

        result = await handler.handle(context, state, history)

        assert result.strategy == "try_different_tier"

    @pytest.mark.asyncio
    async def test_llm_selection_fallback_on_invalid_response(self, mock_llm):
        """Test LLM selection falls back on invalid response."""
        mock_response = MagicMock()
        mock_response.content = "Invalid response without JSON"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        handler = FailureHandler(llm=mock_llm)
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results",
            failed_action="search_rag",
            failed_input={},
            attempt_count=1,
        )

        result = await handler.handle(context, state, history)

        # Should fallback to first strategy
        assert result.strategy == "broaden_query"

    @pytest.mark.asyncio
    async def test_llm_selection_fallback_on_exception(self, mock_llm):
        """Test LLM selection falls back on exception."""
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM error"))

        handler = FailureHandler(llm=mock_llm)
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results",
            failed_action="search_rag",
            failed_input={},
            attempt_count=1,
        )

        result = await handler.handle(context, state, history)

        # Should fallback to first strategy
        assert result.strategy == "broaden_query"

    @pytest.mark.asyncio
    async def test_llm_selection_rejects_unavailable_strategy(self, mock_llm):
        """Test LLM selection rejects strategy not in available list."""
        mock_response = MagicMock()
        # LLM suggests a strategy not in available list
        mock_response.content = '{"chosen_strategy": "invalid_strategy"}'
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        handler = FailureHandler(llm=mock_llm)
        state = WorkingMemory(goal="Test", original_hypothesis="Test")
        history = ExecutionHistory()

        context = FailureContext(
            failure_type=FailureType.SEARCH_NO_RESULTS,
            error_message="No results",
            failed_action="search_rag",
            failed_input={},
            attempt_count=1,
        )

        result = await handler.handle(context, state, history)

        # Should fallback to first available strategy
        assert result.strategy == "broaden_query"
