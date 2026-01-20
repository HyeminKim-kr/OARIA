"""Agent state definitions for LangGraph."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict

from app.schemas.chat import Reference


class ComplexityLevel(str, Enum):
    """Query complexity levels."""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class ToolType(str, Enum):
    """Available tools for task execution."""

    RAG_SEARCH = "rag_search"
    COMPARE = "compare"
    SUMMARIZE = "summarize"


@dataclass
class SubTask:
    """A decomposed sub-task from a complex query."""

    id: str  # e.g., "task_1", "task_2"
    query: str  # Sub-query to execute
    reasoning: str  # Why this sub-task is needed
    tool: ToolType  # Tool to use for this task
    depends_on: list[str] = field(default_factory=list)  # Task IDs this depends on
    status: str = "pending"  # pending, running, completed, failed


@dataclass
class TaskResult:
    """Result from executing a sub-task."""

    task_id: str
    content: str  # Retrieved or generated content
    references: list[Reference] = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None
    # Gate 2: Retrieval Confidence (OAR-12)
    gate2_passed: bool | None = None  # None for non-RAG tasks
    gate2_reason: str | None = None  # low_similarity | insufficient_docs | domain_mismatch
    gate2_tips: list[str] | None = None  # Tips shown in message area
    gate2_suggestions: list[str] | None = None  # Clickable question buttons


class AgentState(TypedDict, total=False):
    """
    State for the agent graph.

    This TypedDict defines the shape of state passed between nodes in LangGraph.
    Using total=False allows partial updates at each node.
    """

    # Input
    query: str  # Original user query
    conversation_id: str | None  # Optional conversation context

    # Complexity analysis (OAR-47)
    complexity: ComplexityLevel  # simple/medium/complex
    complexity_reasoning: str  # Why this complexity level

    # Task decomposition (OAR-48)
    subtasks: list[SubTask]  # Decomposed tasks
    execution_plan: list[str]  # Ordered task IDs for execution

    # Task execution (OAR-50)
    task_results: dict[str, TaskResult]  # Results keyed by task_id
    current_task_id: str | None  # Currently executing task

    # Synthesis (OAR-51)
    final_answer: str  # Synthesized final answer
    citations: list[Reference]  # All citations from all tasks

    # Metadata
    error: str | None  # Error message if failed
    total_duration_ms: int  # Total execution time


def create_initial_state(query: str, conversation_id: str | None = None) -> AgentState:
    """Create initial state for a new agent run."""
    return AgentState(
        query=query,
        conversation_id=conversation_id,
        complexity=ComplexityLevel.SIMPLE,
        complexity_reasoning="",
        subtasks=[],
        execution_plan=[],
        task_results={},
        current_task_id=None,
        final_answer="",
        citations=[],
        error=None,
        total_duration_ms=0,
    )
