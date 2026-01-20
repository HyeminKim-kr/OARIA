"""Agent request/response schemas for F-04."""

from pydantic import BaseModel, Field
from uuid import UUID

from .chat import AskFilters, Reference


class AgentAskRequest(BaseModel):
    """Request for agent-based query processing."""

    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    filters: AskFilters | None = None


class SubTaskSchema(BaseModel):
    """Schema for a decomposed sub-task."""

    id: str
    query: str
    tool: str
    depends_on: list[str] = []


class ComplexityEvent(BaseModel):
    """SSE event for complexity analysis result."""

    level: str  # simple, medium, complex
    reasoning: str


class SubtasksEvent(BaseModel):
    """SSE event for decomposed sub-tasks."""

    tasks: list[SubTaskSchema]


class TaskStartEvent(BaseModel):
    """SSE event when a task starts executing."""

    task_id: str
    query: str


class TaskCompleteEvent(BaseModel):
    """SSE event when a task completes."""

    task_id: str
    summary: str
    references_count: int
    duration_ms: int


class AgentStatusEvent(BaseModel):
    """SSE event for agent status updates."""

    step: str  # analyzing, decomposing, executing, synthesizing
    message: str


class AgentDoneEvent(BaseModel):
    """SSE event when agent processing completes."""

    conversation_id: str
    message_id: str


class AgentExecutionMetadata(BaseModel):
    """Metadata about agent execution for AnswerLog."""

    complexity: str
    complexity_reasoning: str
    subtasks: list[dict]
    total_subtasks: int
    parallel_tasks: int
    total_duration_ms: int
