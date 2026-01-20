"""논문별 채팅 스키마

논문 상세 페이지에서 사용하는 채팅 API의 요청/응답 스키마.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.chat import Reference


# ========================================
# Ask API
# ========================================


class PaperAskRequest(BaseModel):
    """논문별 질의응답 요청"""

    question: str = Field(..., min_length=1, max_length=2000, description="질문 텍스트")
    conversation_id: UUID | None = Field(None, description="기존 대화 ID (없으면 새 대화 생성)")
    include_related: bool = Field(False, description="관련 논문도 검색에 포함할지 여부")
    highlight_context: str | None = Field(None, max_length=5000, description="하이라이트된 텍스트 컨텍스트")


class PaperAskDoneEvent(BaseModel):
    """SSE: done 이벤트"""

    conversation_id: UUID
    message_id: UUID


class PaperAskStatusEvent(BaseModel):
    """SSE: status 이벤트"""

    status: str
    message: str


# ========================================
# Conversation API
# ========================================


class PaperConversationResponse(BaseModel):
    """논문별 대화 응답"""

    id: UUID
    paper_id: UUID
    title: str | None
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None

    class Config:
        from_attributes = True


class PaperConversationListItem(BaseModel):
    """논문별 대화 목록 아이템"""

    id: UUID
    title: str | None
    message_count: int
    last_message_at: datetime | None
    last_message_preview: str | None = None

    class Config:
        from_attributes = True


class PaginatedPaperConversations(BaseModel):
    """페이지네이션된 논문별 대화 목록"""

    items: list[PaperConversationListItem]
    total: int
    page: int
    size: int


# ========================================
# Summary API
# ========================================


SummaryType = Literal["full", "abstract", "methods", "results", "conclusion"]


class SummarizeRequest(BaseModel):
    """요약 생성 요청"""

    type: SummaryType = Field("full", description="요약 유형")
    stream: bool = Field(False, description="스트리밍 응답 여부")


class SummarizeResponse(BaseModel):
    """요약 생성 응답"""

    paper_id: str
    summary_type: str
    summary: str
    sections_used: list[str]
    tokens_used: int
    latency_ms: int


# ========================================
# Citation API
# ========================================


CitationFormat = Literal["apa", "mla", "chicago", "harvard", "vancouver", "bibtex"]


class CitationRequest(BaseModel):
    """인용 정보 요청"""

    format: CitationFormat = Field("apa", description="인용 형식")


class CitationResponse(BaseModel):
    """인용 정보 응답"""

    paper_id: str
    format: str
    citation: str


# ========================================
# Highlight API
# ========================================


class HighlightAskRequest(BaseModel):
    """하이라이트 질문 요청"""

    selected_text: str = Field(..., min_length=1, max_length=5000, description="선택된 텍스트")
    question: str = Field(..., min_length=1, max_length=1000, description="질문")
    section: str | None = Field(None, description="선택 텍스트가 속한 섹션")
    conversation_id: UUID | None = Field(None, description="기존 대화 ID")
