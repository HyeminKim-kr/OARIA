"""Chat/AI 스키마

Pydantic: FastAPI에서 사용하는 데이터 검증 라이브러리
- TypeScript의 interface/type과 유사
- API 요청/응답의 타입과 유효성 정의
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ========================================
# Reference (검색 결과 참조)
# ========================================


class Reference(BaseModel):
    """검색 결과 참조 문헌"""

    paper_id: str
    chunk_id: str
    title: str
    journal: str | None = None
    year: int | None = None
    section: str
    snippet: str
    offset_start: int
    offset_end: int
    text_version: str = "v1"
    distance: float


# ========================================
# Ask AI Request/Response
# ========================================


class AskFilters(BaseModel):
    """검색 필터"""

    year_from: int | None = None
    year_to: int | None = None
    sections: list[str] | None = None


class AskRequest(BaseModel):
    """Ask AI 요청"""

    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    filters: AskFilters | None = None


class AskReferencesEvent(BaseModel):
    """SSE: references 이벤트"""

    references: list[Reference]


class AskTokenEvent(BaseModel):
    """SSE: token 이벤트"""

    token: str


class AskDoneEvent(BaseModel):
    """SSE: done 이벤트"""

    conversation_id: UUID
    message_id: UUID


# ========================================
# Conversation
# ========================================


class ConversationCreate(BaseModel):
    """대화 생성"""

    title: str | None = None


class ConversationUpdate(BaseModel):
    """대화 수정"""

    title: str | None = None
    status: str | None = None


class ConversationResponse(BaseModel):
    """대화 응답"""

    id: UUID
    title: str | None
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None

    class Config:
        from_attributes = True


class ConversationListItem(BaseModel):
    """대화 목록 아이템"""

    id: UUID
    title: str | None
    status: str
    message_count: int
    last_message_at: datetime | None
    last_message_preview: str | None = None

    class Config:
        from_attributes = True


# ========================================
# Message
# ========================================


class MessageCreate(BaseModel):
    """메시지 생성"""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class MessageResponse(BaseModel):
    """메시지 응답"""

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    tokens_used: int | None = None
    model: str | None = None
    latency_ms: int | None = None
    created_at: datetime
    references: list[Reference] | None = None

    class Config:
        from_attributes = True


# ========================================
# Answer Log
# ========================================


class AnswerLogResponse(BaseModel):
    """답변 로그 응답"""

    id: UUID
    question: str
    answer: str
    evidence: list[Reference]
    model: str | None = None
    total_tokens: int | None = None
    total_latency_ms: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ========================================
# Paginated Response
# ========================================


class PaginatedConversations(BaseModel):
    """페이지네이션된 대화 목록"""

    items: list[ConversationListItem]
    total: int
    page: int
    size: int
    pages: int


class PaginatedMessages(BaseModel):
    """페이지네이션된 메시지 목록"""

    items: list[MessageResponse]
    total: int
    page: int
    size: int
    pages: int
