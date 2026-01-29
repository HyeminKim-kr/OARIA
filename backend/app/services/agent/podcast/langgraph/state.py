"""Podcast agent state definitions.

F-11: Agentic Podcast System
- Fixed 3-task structure (RAG → Analysis → Script)
- Only 1 RAG call, results reused across tasks
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict

from app.schemas.chat import Reference


class PodcastTaskType(str, Enum):
    """Podcast agent task types."""

    RAG_SEARCH = "rag_search"        # Task 1: 유일한 RAG 호출
    PAPER_ANALYSIS = "paper_analysis"  # Task 2: 논문 분석 (LLM)
    SCRIPT_GENERATION = "script_generation"  # Task 3: 스크립트 생성 (LLM)


class PodcastStatus(str, Enum):
    """Podcast generation status."""

    PENDING = "pending"
    SEARCHING = "searching"      # Task 1 실행 중
    ANALYZING = "analyzing"       # Task 2 실행 중
    SCRIPTING = "scripting"       # Task 3 실행 중
    GENERATING_AUDIO = "generating_audio"  # TTS 생성 중
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PodcastTaskResult:
    """Result from executing a podcast task."""

    task_type: PodcastTaskType
    status: str = "pending"  # pending, running, completed, failed
    duration_ms: int = 0
    error: str | None = None

    # Task 1 (RAG Search) specific
    references: list[Reference] = field(default_factory=list)
    context: str = ""
    gate2_passed: bool | None = None
    gate2_reason: str | None = None

    # Task 2 (Paper Analysis) specific
    key_findings: list[str] = field(default_factory=list)
    analysis_summary: str = ""
    paper_recommendations: list[dict[str, Any]] = field(default_factory=list)

    # Task 3 (Script Generation) specific
    script: dict[str, Any] | None = None  # DialogueScript as dict


@dataclass
class DialogueTurn:
    """A single turn in the dialogue."""

    speaker: str  # "Alex" or "Sam"
    text: str
    citations: list[int] = field(default_factory=list)  # [1, 3] 형태


@dataclass
class DialogueScript:
    """Complete podcast dialogue script."""

    title: str
    description: str
    speakers: list[str]
    turns: list[DialogueTurn]
    total_estimated_duration: int  # seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "description": self.description,
            "speakers": self.speakers,
            "turns": [
                {
                    "speaker": t.speaker,
                    "text": t.text,
                    "citations": t.citations,
                }
                for t in self.turns
            ],
            "total_estimated_duration": self.total_estimated_duration,
        }


class PodcastState(TypedDict, total=False):
    """
    State for the podcast agent.

    Fixed 3-task structure:
    1. RAG Search (only RAG call)
    2. Paper Analysis (LLM, uses Task 1 results)
    3. Script Generation (LLM, uses Task 1 & 2 results)
    """

    # Input configuration
    goal: str  # User's podcast goal
    duration: str  # short/medium/long
    style: str  # two_hosts/interview/solo
    paper_mode: str  # auto/user_pick/compare
    language: str  # ko/en
    filters: dict[str, Any] | None  # Search filters

    # user_pick mode: 사용자가 선택한 논문들
    selected_paper_ids: list[str] | None

    # Task results (3 tasks)
    task_results: dict[str, PodcastTaskResult]  # keyed by task type
    current_task: PodcastTaskType | None

    # Final outputs
    script: DialogueScript | None
    references: list[Reference]  # From Task 1, used for citations

    # Status
    status: PodcastStatus
    error: str | None
    total_duration_ms: int


def create_initial_podcast_state(
    goal: str,
    duration: str = "short",
    style: str = "two_hosts",
    paper_mode: str = "auto",
    language: str = "ko",
    filters: dict[str, Any] | None = None,
) -> PodcastState:
    """Create initial state for a new podcast generation."""
    return PodcastState(
        # Input
        goal=goal,
        duration=duration,
        style=style,
        paper_mode=paper_mode,
        language=language,
        filters=filters,

        # user_pick mode
        selected_paper_ids=None,

        # Task results (initialized empty)
        task_results={},
        current_task=None,

        # Final outputs
        script=None,
        references=[],

        # Status
        status=PodcastStatus.PENDING,
        error=None,
        total_duration_ms=0,
    )
