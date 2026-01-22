"""Pytest fixtures for v4 agent tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from langchain_openai import ChatOpenAI

from app.services.agent.study_plan.v4.core.state import (
    WorkingMemory,
    ExecutionHistory,
    ExecutionStep,
)
from app.services.agent.study_plan.v4.core.types import Action, Observation
from app.services.agent.study_plan.v4.tools.registry import ToolRegistry
from app.services.agent.study_plan.v4.tools.base import BaseTool, ToolParameter


# ─────────────────────────────────────────────────────────────
# Mock LLM
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm():
    """Create a mock LLM that returns predefined responses."""
    llm = MagicMock(spec=ChatOpenAI)
    llm.ainvoke = AsyncMock()
    return llm


@pytest.fixture
def mock_llm_with_response(mock_llm):
    """Factory fixture to create LLM with specific response."""

    def _create(response_content: str):
        mock_response = MagicMock()
        mock_response.content = response_content
        mock_llm.ainvoke.return_value = mock_response
        return mock_llm

    return _create


# ─────────────────────────────────────────────────────────────
# Sample Data
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_hypothesis():
    """Sample hypothesis for testing."""
    return "EGFR T790M mutation causes osimertinib resistance via MET amplification"


@pytest.fixture
def sample_structured_hypothesis():
    """Sample structured hypothesis."""
    return {
        "iv": "EGFR T790M mutation",
        "dv": "osimertinib resistance",
        "mediators": ["MET amplification"],
        "moderators": [],
        "mechanism": "bypass signaling",
        "confidence": 0.85,
    }


@pytest.fixture
def sample_test_questions():
    """Sample NSPE test questions."""
    return [
        {
            "id": "Q1",
            "category": "necessity",
            "question": "Is MET amplification necessary for osimertinib resistance?",
            "priority": "high",
        },
        {
            "id": "Q2",
            "category": "sufficiency",
            "question": "Is MET amplification sufficient to cause resistance?",
            "priority": "high",
        },
        {
            "id": "Q3",
            "category": "pathway",
            "question": "What is the downstream signaling pathway?",
            "priority": "medium",
        },
    ]


@pytest.fixture
def sample_experiment():
    """Sample experiment design."""
    return {
        "id": "EXP-001",
        "name": "MET knockdown experiment",
        "objective": "Test necessity of MET amplification",
        "approach": "in_vitro",
        "model_system": {
            "type": "cell_line",
            "name": "H1975",
            "rationale": "EGFR T790M positive cell line",
        },
        "groups": [
            {"name": "Control", "treatment": "Scrambled siRNA", "n": 6},
            {"name": "MET KD", "treatment": "MET siRNA", "n": 6},
        ],
    }


# ─────────────────────────────────────────────────────────────
# Working Memory Fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def empty_working_memory(sample_hypothesis):
    """Create empty working memory."""
    return WorkingMemory(
        goal="Generate research plan",
        original_hypothesis=sample_hypothesis,
    )


@pytest.fixture
def populated_working_memory(
    sample_hypothesis,
    sample_structured_hypothesis,
    sample_test_questions,
    sample_experiment,
):
    """Create working memory with some data."""
    memory = WorkingMemory(
        goal="Generate research plan",
        original_hypothesis=sample_hypothesis,
        structured_hypothesis=sample_structured_hypothesis,
        hypothesis_confidence=0.85,
        test_questions=sample_test_questions,
        experiments=[sample_experiment],
        quality_score=0.75,
    )
    return memory


@pytest.fixture
def complete_working_memory(populated_working_memory):
    """Create working memory that meets goal requirements."""
    memory = populated_working_memory
    memory.quality_score = 0.85
    memory.controls["EXP-001"] = [
        {"type": "vehicle", "name": "DMSO control"},
        {"type": "positive", "name": "Known inhibitor"},
    ]
    memory.measurements = [
        {"target": "MET amplification", "assay": "qPCR"},
        {"target": "osimertinib resistance", "assay": "Cell viability"},
        {"target": "EGFR T790M mutation", "assay": "Sequencing"},
    ]
    memory.plan_a = "# Research Plan\n\n## Summary\nTest plan..."
    return memory


# ─────────────────────────────────────────────────────────────
# Execution History Fixtures
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def empty_execution_history():
    """Create empty execution history."""
    return ExecutionHistory()


@pytest.fixture
def execution_history_with_steps():
    """Create execution history with some steps."""
    from datetime import datetime

    history = ExecutionHistory()

    steps = [
        ExecutionStep(
            step_number=1,
            timestamp=datetime.utcnow(),
            thought="Need to parse hypothesis first",
            action="parse_hypothesis",
            action_input={"hypothesis": "test hypothesis"},
            observation={"iv": "X", "dv": "Y"},
            success=True,
            duration_ms=100,
        ),
        ExecutionStep(
            step_number=2,
            timestamp=datetime.utcnow(),
            thought="Now decompose into questions",
            action="decompose_questions",
            action_input={"structured_hypothesis": {}},
            observation={"questions": []},
            success=True,
            duration_ms=150,
        ),
    ]

    for step in steps:
        history.add_step(step)

    return history


# ─────────────────────────────────────────────────────────────
# Tool Fixtures
# ─────────────────────────────────────────────────────────────


class MockTool(BaseTool):
    """Mock tool for testing."""

    def __init__(self, name: str = "mock_tool", result: dict = None):
        self._name = name
        self._result = result or {"success": True}

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock tool: {self._name}"

    @property
    def category(self) -> str:
        return "test"

    def _get_parameters(self):
        return [
            ToolParameter(
                name="input",
                type="str",
                description="Test input",
                required=False,
            )
        ]

    async def run(self, **kwargs):
        return self._result


@pytest.fixture
def mock_tool():
    """Create a single mock tool."""
    return MockTool()


@pytest.fixture
def mock_tool_registry():
    """Create a registry with mock tools."""
    registry = ToolRegistry()

    # Add mock tools for each category
    registry.register(MockTool("parse_hypothesis", {"iv": "X", "dv": "Y", "confidence": 0.9}))
    registry.register(MockTool("decompose_questions", {"questions": [{"id": "Q1"}]}))
    registry.register(MockTool("search_rag", {"papers": [], "coverage": 0.5}))
    registry.register(MockTool("design_experiment", {"experiment": {"id": "EXP-001"}}))
    registry.register(MockTool("design_controls", {"controls": [{"type": "vehicle"}]}))
    registry.register(MockTool("critique_design", {"score": 0.8, "issues": []}))
    registry.register(MockTool("synthesize_plan", {"plan": "# Plan", "summary": "Summary"}))

    return registry


@pytest.fixture
def failing_tool():
    """Create a tool that always fails."""

    class FailingTool(BaseTool):
        @property
        def name(self):
            return "failing_tool"

        @property
        def description(self):
            return "Always fails"

        async def run(self, **kwargs):
            raise Exception("Intentional failure")

    return FailingTool()
