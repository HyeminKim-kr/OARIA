"""Tests for v4 state management - WorkingMemory and ExecutionHistory."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from app.services.agent.study_plan.v4.core.state import (
    WorkingMemory,
    ExecutionHistory,
    ExecutionStep,
)


# ─────────────────────────────────────────────────────────────
# ExecutionStep Tests
# ─────────────────────────────────────────────────────────────


class TestExecutionStep:
    """Test ExecutionStep dataclass."""

    def test_create_successful_step(self):
        """Test creating a successful execution step."""
        step = ExecutionStep(
            step_number=1,
            timestamp=datetime.utcnow(),
            thought="Need to parse the hypothesis first",
            action="parse_hypothesis",
            action_input={"hypothesis": "X causes Y"},
            observation={"iv": "X", "dv": "Y"},
            success=True,
            duration_ms=150,
        )

        assert step.step_number == 1
        assert step.action == "parse_hypothesis"
        assert step.success is True
        assert step.error is None
        assert step.duration_ms == 150

    def test_create_failed_step(self):
        """Test creating a failed execution step."""
        step = ExecutionStep(
            step_number=2,
            timestamp=datetime.utcnow(),
            thought="Search for evidence",
            action="search_rag",
            action_input={"query": "test"},
            observation={"error": "Connection timeout"},
            success=False,
            error="Connection timeout",
            duration_ms=5000,
        )

        assert step.success is False
        assert step.error == "Connection timeout"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        timestamp = datetime.utcnow()
        step = ExecutionStep(
            step_number=1,
            timestamp=timestamp,
            thought="Test thought",
            action="test_action",
            action_input={"key": "value"},
            observation={"result": "data"},
            success=True,
            duration_ms=100,
        )

        step_dict = step.to_dict()

        assert step_dict["step_number"] == 1
        assert step_dict["timestamp"] == timestamp.isoformat()
        assert step_dict["thought"] == "Test thought"
        assert step_dict["action"] == "test_action"
        assert step_dict["action_input"] == {"key": "value"}
        assert step_dict["observation"] == {"result": "data"}
        assert step_dict["success"] is True
        assert step_dict["error"] is None
        assert step_dict["duration_ms"] == 100


# ─────────────────────────────────────────────────────────────
# ExecutionHistory Tests
# ─────────────────────────────────────────────────────────────


class TestExecutionHistory:
    """Test ExecutionHistory class."""

    def test_initialization(self):
        """Test empty history initialization."""
        history = ExecutionHistory()

        assert len(history.steps) == 0
        assert len(history.failed_actions) == 0
        assert history._action_sequence == []

    def test_add_step(self):
        """Test adding a step to history."""
        history = ExecutionHistory()
        step = ExecutionStep(
            step_number=1,
            timestamp=datetime.utcnow(),
            thought="First step",
            action="parse_hypothesis",
            action_input={},
            observation={},
            success=True,
        )

        history.add_step(step)

        assert len(history.steps) == 1
        assert history._action_sequence == ["parse_hypothesis"]

    def test_add_failed_step_tracks_failure(self):
        """Test that failed steps are tracked."""
        history = ExecutionHistory()
        step = ExecutionStep(
            step_number=1,
            timestamp=datetime.utcnow(),
            thought="Failed step",
            action="search_rag",
            action_input={},
            observation={},
            success=False,
            error="Error",
        )

        history.add_step(step)

        assert history.failed_actions["search_rag"] == 1

    def test_multiple_failures_increment_count(self):
        """Test that multiple failures increment count."""
        history = ExecutionHistory()

        for i in range(3):
            step = ExecutionStep(
                step_number=i + 1,
                timestamp=datetime.utcnow(),
                thought=f"Attempt {i + 1}",
                action="search_epmc",
                action_input={},
                observation={},
                success=False,
                error="Failed",
            )
            history.add_step(step)

        assert history.failed_actions["search_epmc"] == 3

    def test_get_recent(self):
        """Test getting recent steps."""
        history = ExecutionHistory()

        for i in range(10):
            step = ExecutionStep(
                step_number=i + 1,
                timestamp=datetime.utcnow(),
                thought=f"Step {i + 1}",
                action=f"action_{i}",
                action_input={},
                observation={},
                success=True,
            )
            history.add_step(step)

        recent = history.get_recent(3)

        assert len(recent) == 3
        assert recent[0].step_number == 8
        assert recent[2].step_number == 10

    def test_get_recent_less_than_n(self):
        """Test get_recent when fewer steps than n."""
        history = ExecutionHistory()
        step = ExecutionStep(
            step_number=1,
            timestamp=datetime.utcnow(),
            thought="Only step",
            action="action",
            action_input={},
            observation={},
            success=True,
        )
        history.add_step(step)

        recent = history.get_recent(5)

        assert len(recent) == 1

    def test_should_avoid_after_two_failures(self):
        """Test should_avoid returns True after 2 failures."""
        history = ExecutionHistory()

        # Add 2 failed steps for same action
        for i in range(2):
            step = ExecutionStep(
                step_number=i + 1,
                timestamp=datetime.utcnow(),
                thought=f"Attempt {i + 1}",
                action="flaky_action",
                action_input={},
                observation={},
                success=False,
                error="Failed",
            )
            history.add_step(step)

        assert history.should_avoid("flaky_action") is True

    def test_should_avoid_returns_false_before_two_failures(self):
        """Test should_avoid returns False before 2 failures."""
        history = ExecutionHistory()

        step = ExecutionStep(
            step_number=1,
            timestamp=datetime.utcnow(),
            thought="First attempt",
            action="flaky_action",
            action_input={},
            observation={},
            success=False,
            error="Failed",
        )
        history.add_step(step)

        assert history.should_avoid("flaky_action") is False

    def test_should_avoid_unknown_action(self):
        """Test should_avoid returns False for unknown action."""
        history = ExecutionHistory()

        assert history.should_avoid("unknown_action") is False

    def test_detect_loop_no_loop(self):
        """Test detect_loop returns False when no loop."""
        history = ExecutionHistory()

        actions = ["a", "b", "c", "d", "e", "f", "g", "h"]
        for i, action in enumerate(actions):
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

        assert history.detect_loop(window=4) is False

    def test_detect_loop_with_loop(self):
        """Test detect_loop returns True when loop detected."""
        history = ExecutionHistory()

        # Create repeating pattern
        pattern = ["parse", "search", "design", "critique"]
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

    def test_detect_loop_insufficient_steps(self):
        """Test detect_loop returns False with insufficient steps."""
        history = ExecutionHistory()

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

    def test_get_context_for_llm_empty(self):
        """Test get_context_for_llm with empty history."""
        history = ExecutionHistory()

        context = history.get_context_for_llm()

        assert context == "No previous actions."

    def test_get_context_for_llm_with_steps(self, execution_history_with_steps):
        """Test get_context_for_llm with steps."""
        context = execution_history_with_steps.get_context_for_llm()

        assert "[SUCCESS]" in context
        assert "parse_hypothesis" in context
        assert "decompose_questions" in context

    def test_get_context_for_llm_truncates_long_thoughts(self):
        """Test that get_context_for_llm truncates long thoughts."""
        history = ExecutionHistory()
        long_thought = "A" * 200

        step = ExecutionStep(
            step_number=1,
            timestamp=datetime.utcnow(),
            thought=long_thought,
            action="test",
            action_input={},
            observation={},
            success=True,
        )
        history.add_step(step)

        context = history.get_context_for_llm()

        assert "..." in context
        assert len(context) < 200

    def test_get_successful_actions(self):
        """Test getting list of successful actions."""
        history = ExecutionHistory()

        steps = [
            ("action_a", True),
            ("action_b", False),
            ("action_c", True),
            ("action_d", True),
        ]

        for i, (action, success) in enumerate(steps):
            step = ExecutionStep(
                step_number=i + 1,
                timestamp=datetime.utcnow(),
                thought=f"Step {i}",
                action=action,
                action_input={},
                observation={},
                success=success,
            )
            history.add_step(step)

        successful = history.get_successful_actions()

        assert successful == ["action_a", "action_c", "action_d"]
        assert "action_b" not in successful

    def test_to_trace(self, execution_history_with_steps):
        """Test converting history to trace."""
        trace = execution_history_with_steps.to_trace()

        assert isinstance(trace, list)
        assert len(trace) == 2
        assert all(isinstance(step, dict) for step in trace)
        assert trace[0]["step_number"] == 1
        assert trace[1]["step_number"] == 2


# ─────────────────────────────────────────────────────────────
# WorkingMemory Tests
# ─────────────────────────────────────────────────────────────


class TestWorkingMemory:
    """Test WorkingMemory dataclass."""

    def test_initialization_with_minimal_args(self):
        """Test initialization with minimal arguments."""
        memory = WorkingMemory(
            goal="Generate plan",
            original_hypothesis="X causes Y",
        )

        assert memory.goal == "Generate plan"
        assert memory.original_hypothesis == "X causes Y"
        assert memory.run_id is not None
        assert memory.iteration_count == 0
        assert memory.total_cost == 0.0

    def test_initialization_with_all_args(self):
        """Test initialization with all arguments."""
        memory = WorkingMemory(
            goal="Generate plan",
            original_hypothesis="X causes Y",
            research_context="Cancer research",
            constraints=["In vitro only"],
            preferred_experiment_types=["cell_line"],
        )

        assert memory.research_context == "Cancer research"
        assert memory.constraints == ["In vitro only"]
        assert memory.preferred_experiment_types == ["cell_line"]

    def test_increment_iteration(self, empty_working_memory):
        """Test incrementing iteration counter."""
        assert empty_working_memory.iteration_count == 0

        empty_working_memory.increment_iteration()

        assert empty_working_memory.iteration_count == 1

        empty_working_memory.increment_iteration()

        assert empty_working_memory.iteration_count == 2

    def test_add_cost(self, empty_working_memory):
        """Test adding cost."""
        assert empty_working_memory.total_cost == 0.0

        empty_working_memory.add_cost(0.5)

        assert empty_working_memory.total_cost == 0.5

        empty_working_memory.add_cost(0.3)

        assert empty_working_memory.total_cost == 0.8

    def test_get_summary(self, populated_working_memory):
        """Test getting state summary."""
        summary = populated_working_memory.get_summary()

        assert isinstance(summary, str)
        assert "Current Progress" in summary
        assert "Hypothesis" in summary
        assert "Research" in summary
        assert "Design" in summary
        assert "Validation" in summary

    def test_get_summary_includes_data(self, populated_working_memory):
        """Test that summary includes actual data."""
        summary = populated_working_memory.get_summary()

        # Should show test questions count
        assert "Test Questions:" in summary
        # Should show experiments count
        assert "Experiments Designed:" in summary

    def test_get_hypothesis_variables_empty(self, empty_working_memory):
        """Test get_hypothesis_variables with no structured hypothesis."""
        variables = empty_working_memory.get_hypothesis_variables()

        assert variables == set()

    def test_get_hypothesis_variables(self, sample_structured_hypothesis):
        """Test get_hypothesis_variables extracts all variables."""
        memory = WorkingMemory(
            goal="Test",
            original_hypothesis="Test",
            structured_hypothesis=sample_structured_hypothesis,
        )

        variables = memory.get_hypothesis_variables()

        assert "EGFR T790M mutation" in variables
        assert "osimertinib resistance" in variables
        assert "MET amplification" in variables

    def test_to_dict(self, populated_working_memory):
        """Test serialization to dictionary."""
        data = populated_working_memory.to_dict()

        assert isinstance(data, dict)
        assert data["run_id"] == populated_working_memory.run_id
        assert data["goal"] == populated_working_memory.goal
        assert data["original_hypothesis"] == populated_working_memory.original_hypothesis
        assert data["quality_score"] == populated_working_memory.quality_score
        assert isinstance(data["started_at"], str)  # ISO format

    def test_to_dict_includes_all_fields(self, complete_working_memory):
        """Test that to_dict includes all fields."""
        data = complete_working_memory.to_dict()

        expected_keys = [
            "run_id",
            "started_at",
            "goal",
            "original_hypothesis",
            "research_context",
            "constraints",
            "preferred_experiment_types",
            "structured_hypothesis",
            "hypothesis_confidence",
            "test_questions",
            "answered_questions",
            "retrieved_papers",
            "evidence_snippets",
            "search_coverage",
            "search_tiers_used",
            "experiments",
            "controls",
            "measurements",
            "validation_results",
            "quality_score",
            "critique_history",
            "plan_a",
            "plan_b",
            "executive_summary",
            "iteration_count",
            "total_cost",
            "user_questions",
        ]

        for key in expected_keys:
            assert key in data, f"Missing key: {key}"


# ─────────────────────────────────────────────────────────────
# WorkingMemory State Modification Tests
# ─────────────────────────────────────────────────────────────


class TestWorkingMemoryModification:
    """Test modifying WorkingMemory state."""

    def test_add_experiment(self, empty_working_memory):
        """Test adding experiments to memory."""
        experiment = {"id": "EXP-001", "name": "Test experiment"}

        empty_working_memory.experiments.append(experiment)

        assert len(empty_working_memory.experiments) == 1
        assert empty_working_memory.experiments[0]["id"] == "EXP-001"

    def test_add_controls(self, empty_working_memory):
        """Test adding controls to memory."""
        exp_id = "EXP-001"
        controls = [
            {"type": "vehicle", "name": "DMSO"},
            {"type": "positive", "name": "Known inhibitor"},
        ]

        empty_working_memory.controls[exp_id] = controls

        assert exp_id in empty_working_memory.controls
        assert len(empty_working_memory.controls[exp_id]) == 2

    def test_add_test_questions(self, empty_working_memory):
        """Test adding test questions to memory."""
        questions = [
            {"id": "Q1", "question": "Is X necessary?"},
            {"id": "Q2", "question": "Is X sufficient?"},
        ]

        empty_working_memory.test_questions = questions

        assert len(empty_working_memory.test_questions) == 2

    def test_update_quality_score(self, empty_working_memory):
        """Test updating quality score."""
        empty_working_memory.quality_score = 0.85

        assert empty_working_memory.quality_score == 0.85

    def test_set_structured_hypothesis(self, empty_working_memory):
        """Test setting structured hypothesis."""
        structured = {
            "iv": "Drug A",
            "dv": "Tumor growth",
            "mediators": ["Apoptosis"],
        }

        empty_working_memory.structured_hypothesis = structured

        assert empty_working_memory.structured_hypothesis == structured

    def test_add_evidence_snippets(self, empty_working_memory):
        """Test adding evidence snippets."""
        snippets = [
            {"text": "Evidence 1", "source": "Paper A"},
            {"text": "Evidence 2", "source": "Paper B"},
        ]

        empty_working_memory.evidence_snippets.extend(snippets)

        assert len(empty_working_memory.evidence_snippets) == 2

    def test_add_measurements(self, empty_working_memory):
        """Test adding measurements."""
        measurements = [
            {"target": "Variable X", "assay": "qPCR"},
            {"target": "Variable Y", "assay": "Western blot"},
        ]

        empty_working_memory.measurements.extend(measurements)

        assert len(empty_working_memory.measurements) == 2

    def test_update_search_coverage(self, empty_working_memory):
        """Test updating search coverage."""
        empty_working_memory.search_coverage = 0.75
        empty_working_memory.search_tiers_used.append(1)

        assert empty_working_memory.search_coverage == 0.75
        assert 1 in empty_working_memory.search_tiers_used

    def test_set_final_plan(self, empty_working_memory):
        """Test setting final plan outputs."""
        empty_working_memory.plan_a = "# Research Plan A"
        empty_working_memory.plan_b = "# Research Plan B"
        empty_working_memory.executive_summary = "Summary of the plan"

        assert empty_working_memory.plan_a is not None
        assert empty_working_memory.plan_b is not None
        assert empty_working_memory.executive_summary is not None
