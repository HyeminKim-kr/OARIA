"""Paper API 스키마

논문 검색/조회 API의 요청/응답 스키마
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================
# Author 스키마
# ============================================================
class AuthorResponse(BaseModel):
    """저자 응답"""

    author_name: str
    author_order: int
    is_corresponding: bool = False
    orcid: Optional[str] = None
    affiliation: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================
# Paper 스키마
# ============================================================
class PaperListItem(BaseModel):
    """논문 목록 아이템 (간략 정보)"""

    id: UUID
    paper_id: str
    pmcid: Optional[str] = None
    pmid: Optional[str] = None
    doi: Optional[str] = None
    title: str
    abstract: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[int] = None
    keywords: Optional[list[str]] = None
    is_open_access: bool = True
    created_at: datetime

    # 저자 (첫 번째 저자만 또는 전체)
    authors: list[AuthorResponse] = []

    model_config = {"from_attributes": True}


class PaperDetail(PaperListItem):
    """논문 상세 정보"""

    source: str = "europe_pmc"
    source_url: Optional[str] = None
    status: str = "collected"
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# Search 스키마
# ============================================================
class PaperSearchParams(BaseModel):
    """논문 검색 파라미터"""

    q: Optional[str] = Field(None, description="검색어 (제목, 초록)")
    year_from: Optional[int] = Field(None, description="시작 연도")
    year_to: Optional[int] = Field(None, description="종료 연도")
    keyword: Optional[str] = Field(None, description="키워드 필터")
    page: int = Field(1, ge=1, description="페이지 번호")
    limit: int = Field(20, ge=1, le=100, description="페이지당 항목 수")


class PaginatedResponse(BaseModel):
    """페이지네이션 응답"""

    items: list[PaperListItem]
    total: int
    page: int
    limit: int
    total_pages: int


# ============================================================
# Stats 스키마
# ============================================================
class PaperStats(BaseModel):
    """논문 통계"""

    total: int
    by_year: list[dict]
    recent_count: int  # 최근 7일


# ============================================================
# Section Text (모달 하이라이트용)
# ============================================================
class ParagraphResponse(BaseModel):
    """단락 응답"""
    text: str
    offset_start: int
    offset_end: int


class SectionTextResponse(BaseModel):
    """섹션 풀텍스트 응답 (Weaviate에서 조회) - Legacy"""

    paper_id: str
    section: str
    title: str
    journal: Optional[str] = None
    year: Optional[int] = None
    text: str  # 섹션 전체 텍스트


class SectionContentResponse(BaseModel):
    """섹션 내용 응답 (S3 XML 기반) - 단락 구분 포함"""

    paper_id: str
    section: str
    section_title: str
    title: str  # 논문 제목
    journal: Optional[str] = None
    year: Optional[int] = None
    paragraphs: list[ParagraphResponse]
    total_text: str  # 전체 텍스트 (offset 계산용)
    section_fulltext_offset: int = 0  # fulltext 기준 섹션 시작 위치 (하이라이트 오프셋 변환용)
