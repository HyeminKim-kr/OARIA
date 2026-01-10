"""Tests for F-04 Agent Task Decomposition.

Run with: pytest tests/test_agent.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# ─────────────────────────────────────────────────────────────
# State Tests
# ─────────────────────────────────────────────────────────────


def test_complexity_level_enum():
    """Test ComplexityLevel enum values."""
    from app.services.agent.state import ComplexityLevel

    assert ComplexityLevel.SIMPLE.value == "simple"
    assert ComplexityLevel.MEDIUM.value == "medium"
    assert ComplexityLevel.COMPLEX.value == "complex"


def test_tool_type_enum():
    """Test ToolType enum values."""
    from app.services.agent.state import ToolType

    assert ToolType.RAG_SEARCH.value == "rag_search"
    assert ToolType.COMPARE.value == "compare"
    assert ToolType.SUMMARIZE.value == "summarize"


def test_subtask_dataclass():
    """Test SubTask dataclass creation."""
    from app.services.agent.state import SubTask, ToolType

    task = SubTask(
        id="task_1",
        query="What is EGFR?",
        reasoning="Basic concept lookup",
        tool=ToolType.RAG_SEARCH,
        depends_on=[],
    )

    assert task.id == "task_1"
    assert task.tool == ToolType.RAG_SEARCH
    assert task.status == "pending"


def test_create_initial_state():
    """Test initial state creation."""
    from app.services.agent.state import create_initial_state, ComplexityLevel

    state = create_initial_state("Test query", "conv-123")

    assert state["query"] == "Test query"
    assert state["conversation_id"] == "conv-123"
    assert state["complexity"] == ComplexityLevel.SIMPLE
    assert state["subtasks"] == []
    assert state["error"] is None


# ─────────────────────────────────────────────────────────────
# Graph Routing Tests
# ─────────────────────────────────────────────────────────────


def test_should_decompose_simple():
    """Test routing for simple queries."""
    from app.services.agent.graph import should_decompose
    from app.services.agent.state import ComplexityLevel

    state = {"complexity": ComplexityLevel.SIMPLE}
    assert should_decompose(state) == "direct_rag"


def test_should_decompose_medium():
    """Test routing for medium queries."""
    from app.services.agent.graph import should_decompose
    from app.services.agent.state import ComplexityLevel

    state = {"complexity": ComplexityLevel.MEDIUM}
    assert should_decompose(state) == "decompose"


def test_should_decompose_complex():
    """Test routing for complex queries."""
    from app.services.agent.graph import should_decompose
    from app.services.agent.state import ComplexityLevel

    state = {"complexity": ComplexityLevel.COMPLEX}
    assert should_decompose(state) == "decompose"


# ─────────────────────────────────────────────────────────────
# Complexity Analyzer Tests (Mocked)
# ─────────────────────────────────────────────────────────────


@patch("app.services.agent.nodes.complexity_analyzer.OpenAI")
def test_analyze_complexity_simple(mock_openai):
    """Test complexity analysis for simple query."""
    from app.services.agent.nodes.complexity_analyzer import analyze_complexity
    from app.services.agent.state import ComplexityLevel

    # Mock OpenAI response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"complexity": "simple", "reasoning": "Single concept"}'
    mock_openai.return_value.chat.completions.create.return_value = mock_response

    state = {"query": "EGFR이란 무엇인가?"}
    result = analyze_complexity(state)

    assert result["complexity"] == ComplexityLevel.SIMPLE
    assert "reasoning" in result["complexity_reasoning"].lower() or len(result["complexity_reasoning"]) > 0


@patch("app.services.agent.nodes.complexity_analyzer.OpenAI")
def test_analyze_complexity_complex(mock_openai):
    """Test complexity analysis for complex query."""
    from app.services.agent.nodes.complexity_analyzer import analyze_complexity
    from app.services.agent.state import ComplexityLevel

    # Mock OpenAI response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"complexity": "complex", "reasoning": "Multiple conditions and comparison"}'
    mock_openai.return_value.chat.completions.create.return_value = mock_response

    state = {"query": "EGFR+TP53 이중 변이 환자의 1차 치료 vs 2차 치료 효과 비교"}
    result = analyze_complexity(state)

    assert result["complexity"] == ComplexityLevel.COMPLEX


# ─────────────────────────────────────────────────────────────
# Task Decomposer Tests (Mocked)
# ─────────────────────────────────────────────────────────────


@patch("app.services.agent.nodes.task_decomposer.OpenAI")
def test_decompose_tasks(mock_openai):
    """Test task decomposition."""
    from app.services.agent.nodes.task_decomposer import decompose_tasks
    from app.services.agent.state import ComplexityLevel

    # Mock OpenAI response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '''
    {
        "tasks": [
            {"id": "task_1", "query": "EGFR 변이 특성", "reasoning": "First concept", "tool": "rag_search", "depends_on": []},
            {"id": "task_2", "query": "TP53 변이 영향", "reasoning": "Second concept", "tool": "rag_search", "depends_on": []},
            {"id": "task_3", "query": "치료 비교", "reasoning": "Comparison", "tool": "compare", "depends_on": ["task_1", "task_2"]}
        ],
        "execution_plan": ["task_1", "task_2", "task_3"]
    }
    '''
    mock_openai.return_value.chat.completions.create.return_value = mock_response

    state = {
        "query": "EGFR+TP53 이중 변이 환자의 치료 비교",
        "complexity": ComplexityLevel.COMPLEX,
        "complexity_reasoning": "Multiple conditions",
    }
    result = decompose_tasks(state)

    assert len(result["subtasks"]) == 3
    assert result["execution_plan"] == ["task_1", "task_2", "task_3"]
    assert result["subtasks"][2].depends_on == ["task_1", "task_2"]


# ─────────────────────────────────────────────────────────────
# Tool Router Tests
# ─────────────────────────────────────────────────────────────


def test_route_tools_ordering():
    """Test that tool router orders tasks correctly by dependencies."""
    from app.services.agent.nodes.tool_router import route_tools
    from app.services.agent.state import SubTask, ToolType

    subtasks = [
        SubTask(id="task_3", query="Compare", reasoning="", tool=ToolType.COMPARE, depends_on=["task_1", "task_2"]),
        SubTask(id="task_1", query="EGFR", reasoning="", tool=ToolType.RAG_SEARCH, depends_on=[]),
        SubTask(id="task_2", query="TP53", reasoning="", tool=ToolType.RAG_SEARCH, depends_on=[]),
    ]

    state = {"subtasks": subtasks}
    result = route_tools(state)

    # task_1 and task_2 should come before task_3
    plan = result["execution_plan"]
    assert plan.index("task_3") > plan.index("task_1")
    assert plan.index("task_3") > plan.index("task_2")


# ─────────────────────────────────────────────────────────────
# Schema Tests
# ─────────────────────────────────────────────────────────────


def test_agent_ask_request_validation():
    """Test AgentAskRequest schema validation."""
    from app.schemas.agent import AgentAskRequest

    # Valid request
    request = AgentAskRequest(question="What is EGFR?")
    assert request.question == "What is EGFR?"
    assert request.conversation_id is None

    # With conversation_id
    from uuid import uuid4
    conv_id = uuid4()
    request2 = AgentAskRequest(question="Test", conversation_id=conv_id)
    assert request2.conversation_id == conv_id


def test_agent_ask_request_min_length():
    """Test AgentAskRequest minimum length validation."""
    from app.schemas.agent import AgentAskRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AgentAskRequest(question="")  # Too short


# ─────────────────────────────────────────────────────────────
# Integration Test (requires running services)
# ─────────────────────────────────────────────────────────────


@pytest.mark.skip(reason="Requires running services (Weaviate, OpenAI)")
def test_agent_service_execute():
    """Integration test for full agent execution."""
    from app.services.agent import agent_service

    result = agent_service.execute("EGFR이란 무엇인가?")

    assert result.answer != ""
    assert result.complexity is not None
    assert result.total_duration_ms > 0
