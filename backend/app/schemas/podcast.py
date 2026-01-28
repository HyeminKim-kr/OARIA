"""Podcast 스키마

F-11: Agentic Podcast System
Request/Response schemas for podcast generation
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ========================================
# Enums (문자열로 API 호환성 유지)
# ========================================


# ========================================
# Request Schemas
# ========================================


class PodcastFilters(BaseModel):
    """검색 필터"""

    year_from: int | None = None
    year_to: int | None = None
    min_citations: int | None = None
    sources: list[str] | None = None  # ["pmc", "arxiv", "medrxiv"]
    journal_tiers: list[str] | None = None  # ["tier1", "tier2"]


class PodcastGoalRequest(BaseModel):
    """팟캐스트 생성 요청"""

    goal: str = Field(..., min_length=5, max_length=1000, description="생성 목표 (단일 명확한 목표)")
    duration: str = Field(default="short", pattern="^(short|medium|long)$", description="에피소드 길이")
    style: str = Field(default="two_hosts", pattern="^(two_hosts|interview|solo)$", description="팟캐스트 스타일")
    paper_mode: str = Field(default="auto", pattern="^(auto|user_pick|compare)$", description="논문 선택 모드")
    language: str = Field(default="ko", pattern="^(ko|en)$", description="출력 언어")
    filters: PodcastFilters | None = None


class PaperSelectionRequest(BaseModel):
    """user_pick 모드: 사용자 논문 선택"""

    paper_ids: list[str] = Field(..., min_length=1, max_length=10, description="선택된 논문 ID 목록")


class SubscriptionCreateRequest(BaseModel):
    """구독 생성 요청"""

    topics: list[str] = Field(..., min_length=1, max_length=5, description="구독 주제 목록")
    frequency: str = Field(default="weekly", pattern="^(daily|weekly|monthly)$")
    episode_style: str = Field(default="two_hosts", pattern="^(two_hosts|interview|solo)$")
    episode_duration: str = Field(default="short", pattern="^(short|medium|long)$")
    language: str = Field(default="ko", pattern="^(ko|en)$")


class SubscriptionUpdateRequest(BaseModel):
    """구독 수정 요청"""

    topics: list[str] | None = Field(None, min_length=1, max_length=5)
    frequency: str | None = Field(None, pattern="^(daily|weekly|monthly)$")
    episode_style: str | None = Field(None, pattern="^(two_hosts|interview|solo)$")
    episode_duration: str | None = Field(None, pattern="^(short|medium|long)$")
    language: str | None = Field(None, pattern="^(ko|en)$")
    is_active: bool | None = None


# ========================================
# Response Schemas
# ========================================


class DialogueTurn(BaseModel):
    """대화 턴"""

    speaker: str  # "Alex" or "Sam" (or custom)
    text: str
    citations: list[int] | None = None  # [1, 3] 형태로 인용 번호


class DialogueScript(BaseModel):
    """팟캐스트 스크립트"""

    title: str
    description: str
    speakers: list[str]  # ["Alex", "Sam"]
    turns: list[DialogueTurn]
    total_estimated_duration: int  # seconds


class TurnTiming(BaseModel):
    """턴별 오디오 타이밍 정보"""

    turn_index: int
    start_time: float
    end_time: float
    speaker: str


class PodcastReference(BaseModel):
    """팟캐스트에서 사용된 참조 문헌"""

    index: int  # [1], [2] 등 인용 번호
    paper_id: str
    title: str
    authors: list[str] | None = None
    journal: str | None = None
    year: int | None = None
    snippet: str  # 사용된 부분


class TaskResult(BaseModel):
    """개별 Task 실행 결과"""

    task_name: str
    status: str  # "completed" | "failed"
    duration_ms: int
    output_summary: str | None = None
    error: str | None = None


class EpisodeResponse(BaseModel):
    """에피소드 응답"""

    id: UUID
    goal: str
    title: str | None
    description: str | None
    status: str
    duration: str
    style: str
    language: str

    # Content (완료 시)
    audio_url: str | None = None
    duration_seconds: int | None = None
    script: DialogueScript | None = None
    references: list[PodcastReference] | None = None
    turn_timings: list[TurnTiming] | None = None

    # Metadata
    paper_ids: list[str] | None = None
    task_results: list[TaskResult] | None = None

    # Timestamps
    created_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class EpisodeListItem(BaseModel):
    """에피소드 목록 아이템"""

    id: UUID
    title: str | None
    goal: str
    status: str
    duration_seconds: int | None
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    """구독 응답"""

    id: UUID
    topics: list[str]
    frequency: str
    episode_style: str
    episode_duration: str
    language: str
    is_active: bool
    last_generated_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========================================
# SSE Event Schemas
# ========================================


class PodcastStatusEvent(BaseModel):
    """SSE: 상태 이벤트"""

    status: str  # "searching" | "analyzing" | "scripting" | "generating_audio"
    message: str


class PodcastTaskStartEvent(BaseModel):
    """SSE: 태스크 시작 이벤트"""

    task_name: str
    task_index: int  # 1, 2, 3
    total_tasks: int  # 3


class PodcastTaskCompleteEvent(BaseModel):
    """SSE: 태스크 완료 이벤트"""

    task_name: str
    task_index: int
    duration_ms: int
    summary: str | None = None


class PodcastSearchResultsEvent(BaseModel):
    """SSE: RAG 검색 결과 (user_pick 모드용)"""

    papers: list[dict[str, Any]]  # paper_id, title, abstract, year 등
    message: str


class PodcastScriptChunkEvent(BaseModel):
    """SSE: 스크립트 생성 스트리밍"""

    chunk: str


class PodcastDoneEvent(BaseModel):
    """SSE: 완료 이벤트"""

    episode_id: UUID
    title: str
    audio_url: str
    duration_seconds: int


class PodcastErrorEvent(BaseModel):
    """SSE: 에러 이벤트"""

    error: str
    task: str | None = None


# ========================================
# Paginated Response
# ========================================


class PaginatedEpisodes(BaseModel):
    """페이지네이션된 에피소드 목록"""

    items: list[EpisodeListItem]
    total: int
    page: int
    size: int
    pages: int


class PaginatedSubscriptions(BaseModel):
    """페이지네이션된 구독 목록"""

    items: list[SubscriptionResponse]
    total: int
    page: int
    size: int
    pages: int
