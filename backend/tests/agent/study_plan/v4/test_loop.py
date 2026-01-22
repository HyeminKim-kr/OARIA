"""Tests for AgentLoop - the core ReAct execution loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.agent.study_plan.v4.core.loop import AgentLoop, AgentLoopEvent
from app.services.agent.study_plan.v4.core.state import WorkingMemory, ExecutionHistory
from app.services.agent.study_plan.v4.core.types import Action, Observation, AgentResult
from app.services.agent.study_plan.v4.core.goal_checker import GoalChecker, GoalStatus
from app.services.agent.study_plan.v4.core.failure_handler import FailureHandler


# ─────────────────────────────────────────────────────────────
# AgentLoop Initialization Tests
# ─────────────────────────────────────────────────────────────


class TestAgentLoopInitialization:
    """Test AgentLoop initialization."""

    def test_init_with_defaults(self, mock_llm, mock_tool_registry):
        """Test initialization with default values."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)

        assert loop.llm == mock_llm
        assert loop.tools == mock_tool_registry
        assert loop.max_iterations == 30
        assert loop.reasoner is not None
        assert loop.executor is not None
        assert loop.failure_handler is not None
        assert loop.goal_checker is not None

    def test_init_with_custom_max_iterations(self, mock_llm, mock_tool_registry):
        """Test initialization with custom max iterations."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry, max_iterations=10)

        assert loop.max_iterations == 10

    def test_init_with_custom_handlers(self, mock_llm, mock_tool_registry):
        """Test initialization with custom failure handler and goal checker."""
        custom_failure_handler = FailureHandler(mock_llm)
        custom_goal_checker = GoalChecker()

        loop = AgentLoop(
            llm=mock_llm,
            tools=mock_tool_registry,
            failure_handler=custom_failure_handler,
            goal_checker=custom_goal_checker,
        )

        assert loop.failure_handler == custom_failure_handler
        assert loop.goal_checker == custom_goal_checker


# ─────────────────────────────────────────────────────────────
# AgentLoop.run() Tests
# ─────────────────────────────────────────────────────────────


class TestAgentLoopRun:
    """Test AgentLoop.run() execution."""

    @pytest.mark.asyncio
    async def test_run_completes_on_goal_achieved(self, mock_llm, mock_tool_registry):
        """Test that loop completes when goal is achieved."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)

        # Mock goal checker to return achieved after first iteration
        mock_goal_status = GoalStatus(
            achieved=True,
            details={"all_requirements": True},
            missing=[],
            quality_assessment="All requirements met",
        )
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(return_value=mock_goal_status)

        result = await loop.run(hypothesis="Test hypothesis")

        assert result.success is True
        assert result.iteration_count >= 1
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run_stops_at_max_iterations(self, mock_llm, mock_tool_registry):
        """Test that loop stops when max iterations is reached."""
        max_iter = 3
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry, max_iterations=max_iter)

        # Mock goal checker to never achieve
        mock_goal_status = GoalStatus(
            achieved=False,
            details={},
            missing=["structured_hypothesis", "experiments"],
            quality_assessment="Requirements not met",
        )
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(return_value=mock_goal_status)

        # Mock reasoner to return a valid action
        mock_action = Action(name="parse_hypothesis", input={"hypothesis": "test"})
        loop.reasoner = MagicMock()
        loop.reasoner.reason = AsyncMock(return_value=("Need to parse", mock_action))

        # Mock executor to return success
        mock_observation = Observation(success=True, result={"iv": "X", "dv": "Y"})
        loop.executor = MagicMock()
        loop.executor.execute = AsyncMock(return_value=mock_observation)

        result = await loop.run(hypothesis="Test hypothesis")

        assert result.iteration_count == max_iter
        assert result.success is False
        assert "Missing:" in result.error

    @pytest.mark.asyncio
    async def test_run_stops_on_finish_action(self, mock_llm, mock_tool_registry):
        """Test that loop stops when FINISH action is returned."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)

        # Mock goal checker to not achieve (so we continue to reason)
        mock_goal_status = GoalStatus(
            achieved=False,
            details={},
            missing=["something"],
            quality_assessment="Not complete",
        )
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(return_value=mock_goal_status)

        # Mock reasoner to return FINISH action
        finish_action = Action(name="FINISH", input={})
        loop.reasoner = MagicMock()
        loop.reasoner.reason = AsyncMock(return_value=("Done with plan", finish_action))

        result = await loop.run(hypothesis="Test hypothesis")

        # Should stop after FINISH, not after max iterations
        assert result.iteration_count == 1

    @pytest.mark.asyncio
    async def test_run_handles_action_failure(self, mock_llm, mock_tool_registry):
        """Test that loop handles failed actions and continues."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry, max_iterations=3)

        # Mock goal checker
        mock_goal_status = GoalStatus(
            achieved=False,
            details={},
            missing=["something"],
            quality_assessment="Not complete",
        )
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(return_value=mock_goal_status)

        # Mock reasoner
        mock_action = Action(name="search_rag", input={"query": "test"})
        loop.reasoner = MagicMock()
        loop.reasoner.reason = AsyncMock(return_value=("Searching...", mock_action))

        # Mock executor to fail first, then succeed
        failed_observation = Observation(success=False, error="Connection timeout")
        success_observation = Observation(success=True, result={"papers": []})

        loop.executor = MagicMock()
        loop.executor.execute = AsyncMock(
            side_effect=[failed_observation, success_observation, success_observation]
        )

        # Mock failure handler
        loop.failure_handler = MagicMock()
        loop.failure_handler.classify_failure = MagicMock(return_value="network_error")
        recovery_plan = MagicMock()
        recovery_plan.next_actions = []
        loop.failure_handler.handle = AsyncMock(return_value=recovery_plan)

        result = await loop.run(hypothesis="Test hypothesis")

        # Verify failure handler was called
        loop.failure_handler.handle.assert_called()
        assert result.iteration_count == 3

    @pytest.mark.asyncio
    async def test_run_with_custom_goal(self, mock_llm, mock_tool_registry):
        """Test running with a custom goal."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)

        # Mock immediate goal achievement
        mock_goal_status = GoalStatus(
            achieved=True,
            details={},
            missing=[],
            quality_assessment="Goal achieved",
        )
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(return_value=mock_goal_status)

        custom_goal = "Just parse the hypothesis"
        result = await loop.run(hypothesis="Test hypothesis", goal=custom_goal)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_handles_exception(self, mock_llm, mock_tool_registry):
        """Test that loop handles exceptions gracefully."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)

        # Mock goal checker to raise exception
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(side_effect=Exception("Unexpected error"))

        result = await loop.run(hypothesis="Test hypothesis")

        assert result.success is False
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_run_initializes_state_correctly(self, mock_llm, mock_tool_registry):
        """Test that state is initialized with correct parameters."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)

        # Mock immediate completion
        mock_goal_status = GoalStatus(
            achieved=True,
            details={},
            missing=[],
            quality_assessment="Complete",
        )
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(return_value=mock_goal_status)

        hypothesis = "EGFR mutation causes resistance"
        context = "Cancer research"
        constraints = ["In vitro only"]
        exp_types = ["cell_line"]

        result = await loop.run(
            hypothesis=hypothesis,
            research_context=context,
            constraints=constraints,
            preferred_experiment_types=exp_types,
        )

        assert result.success is True


# ─────────────────────────────────────────────────────────────
# AgentLoop.run_stream() Tests
# ─────────────────────────────────────────────────────────────


class TestAgentLoopStream:
    """Test AgentLoop.run_stream() streaming execution."""

    @pytest.mark.asyncio
    async def test_stream_emits_started_event(self, mock_llm, mock_tool_registry):
        """Test that streaming emits STARTED event first."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)

        # Mock immediate goal achievement
        mock_goal_status = GoalStatus(
            achieved=True,
            details={},
            missing=[],
            quality_assessment="Complete",
        )
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(return_value=mock_goal_status)

        events = []
        async for event_type, event_data in loop.run_stream(hypothesis="Test"):
            events.append((event_type, event_data))

        assert len(events) > 0
        assert events[0][0] == AgentLoopEvent.STARTED
        assert "run_id" in events[0][1]

    @pytest.mark.asyncio
    async def test_stream_emits_completed_event(self, mock_llm, mock_tool_registry):
        """Test that streaming emits COMPLETED event at end."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)

        # Mock immediate goal achievement
        mock_goal_status = GoalStatus(
            achieved=True,
            details={},
            missing=[],
            quality_assessment="Complete",
        )
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(return_value=mock_goal_status)

        events = []
        async for event_type, event_data in loop.run_stream(hypothesis="Test"):
            events.append((event_type, event_data))

        assert events[-1][0] == AgentLoopEvent.COMPLETED
        assert "success" in events[-1][1]

    @pytest.mark.asyncio
    async def test_stream_emits_thinking_and_acting_events(
        self, mock_llm, mock_tool_registry
    ):
        """Test that streaming emits THINKING and ACTING events."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry, max_iterations=2)

        # First check: not achieved, second check: achieved
        mock_goal_not_achieved = GoalStatus(
            achieved=False,
            details={},
            missing=["x"],
            quality_assessment="Not complete",
        )
        mock_goal_achieved = GoalStatus(
            achieved=True,
            details={},
            missing=[],
            quality_assessment="Complete",
        )
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(
            side_effect=[mock_goal_not_achieved, mock_goal_achieved]
        )

        # Mock reasoner
        mock_action = Action(name="parse_hypothesis", input={})
        loop.reasoner = MagicMock()
        loop.reasoner.reason = AsyncMock(return_value=("Thinking...", mock_action))

        # Mock executor
        mock_observation = Observation(success=True, result={"iv": "X"})
        loop.executor = MagicMock()
        loop.executor.execute = AsyncMock(return_value=mock_observation)

        event_types = []
        async for event_type, _ in loop.run_stream(hypothesis="Test"):
            event_types.append(event_type)

        assert AgentLoopEvent.THINKING in event_types
        assert AgentLoopEvent.ACTING in event_types
        assert AgentLoopEvent.OBSERVATION in event_types

    @pytest.mark.asyncio
    async def test_stream_emits_error_event_on_exception(
        self, mock_llm, mock_tool_registry
    ):
        """Test that streaming emits ERROR event on exception."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)

        # Mock goal checker to raise exception
        loop.goal_checker = MagicMock()
        loop.goal_checker.check = MagicMock(side_effect=Exception("Stream error"))

        events = []
        async for event_type, event_data in loop.run_stream(hypothesis="Test"):
            events.append((event_type, event_data))

        assert events[-1][0] == AgentLoopEvent.ERROR
        assert "Stream error" in events[-1][1]["error"]


# ─────────────────────────────────────────────────────────────
# State Update Tests
# ─────────────────────────────────────────────────────────────


class TestStateUpdate:
    """Test _update_state() method."""

    def test_update_state_parse_hypothesis(self, mock_llm, mock_tool_registry):
        """Test state update for parse_hypothesis action."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)
        state = WorkingMemory(goal="Test", original_hypothesis="Test hypothesis")

        action = Action(name="parse_hypothesis", input={})
        observation = Observation(
            success=True,
            result={"iv": "X", "dv": "Y", "confidence": 0.9},
        )

        loop._update_state(state, action, observation)

        assert state.structured_hypothesis == {"iv": "X", "dv": "Y", "confidence": 0.9}
        assert state.hypothesis_confidence == 0.9

    def test_update_state_decompose_questions(self, mock_llm, mock_tool_registry):
        """Test state update for decompose_questions action."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)
        state = WorkingMemory(goal="Test", original_hypothesis="Test hypothesis")

        action = Action(name="decompose_questions", input={})
        questions = [{"id": "Q1", "question": "Is X necessary?"}]
        observation = Observation(
            success=True,
            result={"questions": questions},
        )

        loop._update_state(state, action, observation)

        assert state.test_questions == questions

    def test_update_state_search_rag(self, mock_llm, mock_tool_registry):
        """Test state update for search_rag action."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)
        state = WorkingMemory(goal="Test", original_hypothesis="Test hypothesis")

        action = Action(name="search_rag", input={})
        papers = [{"title": "Paper 1"}]
        snippets = [{"text": "Evidence..."}]
        observation = Observation(
            success=True,
            result={"papers": papers, "snippets": snippets, "coverage": 0.8},
        )

        loop._update_state(state, action, observation)

        assert state.retrieved_papers == papers
        assert state.evidence_snippets == snippets
        assert state.search_coverage == 0.8
        assert 1 in state.search_tiers_used

    def test_update_state_design_experiment(self, mock_llm, mock_tool_registry):
        """Test state update for design_experiment action."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)
        state = WorkingMemory(goal="Test", original_hypothesis="Test hypothesis")

        action = Action(name="design_experiment", input={})
        experiment = {"id": "EXP-001", "name": "Test experiment"}
        observation = Observation(
            success=True,
            result={"experiment": experiment},
        )

        loop._update_state(state, action, observation)

        assert experiment in state.experiments

    def test_update_state_synthesize_plan(self, mock_llm, mock_tool_registry):
        """Test state update for synthesize_plan action."""
        loop = AgentLoop(llm=mock_llm, tools=mock_tool_registry)
        state = WorkingMemory(goal="Test", original_hypothesis="Test hypothesis")

        action = Action(name="synthesize_plan", input={})
        observation = Observation(
            success=True,
            result={"plan": "# Research Plan", "summary": "Summary text"},
        )

        loop._update_state(state, action, observation)

        assert state.plan_a == "# Research Plan"
        assert state.executive_summary == "Summary text"


# ─────────────────────────────────────────────────────────────
# Loop Detection Tests
# ─────────────────────────────────────────────────────────────


class TestLoopDetection:
    """Test loop detection in execution history."""

    def test_detect_loop_returns_false_when_no_loop(self):
        """Test that detect_loop returns False when no loop exists."""
        history = ExecutionHistory()

        # Add varied actions
        actions = ["parse", "search", "design", "critique", "synthesize"]
        for i, action in enumerate(actions):
            from app.services.agent.study_plan.v4.core.state import ExecutionStep

            step = ExecutionStep(
                step_number=i + 1,
                timestamp=datetime.utcnow(),
                thought=f"Step {i}",
                action=action,
                action_input={},
                observation={},
                success=True,
            )
            history.add_step(step)

        assert history.detect_loop() is False

    def test_detect_loop_returns_true_when_loop_exists(self):
        """Test that detect_loop returns True when loop is detected."""
        from app.services.agent.study_plan.v4.core.state import ExecutionStep

        history = ExecutionHistory()

        # Create a repeating pattern: A, B, C, D, A, B, C, D
        pattern = ["action_a", "action_b", "action_c", "action_d"]
        for repeat in range(2):
            for i, action in enumerate(pattern):
                step = ExecutionStep(
                    step_number=repeat * 4 + i + 1,
                    timestamp=datetime.utcnow(),
                    thought=f"Step {repeat * 4 + i}",
                    action=action,
                    action_input={},
                    observation={},
                    success=True,
                )
                history.add_step(step)

        assert history.detect_loop(window=4) is True

    def test_detect_loop_requires_minimum_steps(self):
        """Test that detect_loop requires enough steps to detect."""
        from app.services.agent.study_plan.v4.core.state import ExecutionStep

        history = ExecutionHistory()

        # Only 3 steps - not enough for window=4
        for i in range(3):
            step = ExecutionStep(
                step_number=i + 1,
                timestamp=datetime.utcnow(),
                thought=f"Step {i}",
                action="same_action",
                action_input={},
                observation={},
                success=True,
            )
            history.add_step(step)

        assert history.detect_loop(window=4) is False
