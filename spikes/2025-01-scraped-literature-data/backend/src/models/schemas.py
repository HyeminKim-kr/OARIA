"""
OARIA Literature - Pydantic 스키마

API 요청/응답에 사용되는 Pydantic 모델입니다.
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


# =============================================================================
# Paper Schemas
# =============================================================================

class PaperCreate(BaseModel):
    """논문 생성 요청"""
    pmid: str
    pmcid: Optional[str] = None
    title: str = ""
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    journal: Optional[str] = None
    pubdate: Optional[str] = None
    doi: Optional[str] = None
    mesh_terms: list[str] = Field(default_factory=list)


class PaperResponse(BaseModel):
    """논문 응답"""
    pmid: str
    pmcid: Optional[str] = None
    title: str
    abstract: str
    authors: list[str]
    journal: Optional[str]
    pubdate: Optional[str]
    doi: Optional[str]
    mesh_terms: list[str]
    fulltext_path: Optional[str] = None
    embedding_status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# =============================================================================
# Search Schemas
# =============================================================================

class SearchRequest(BaseModel):
    """PubMed 검색 요청"""
    term: str = Field(..., description="검색 키워드")
    date_from: Optional[str] = Field(None, description="시작일 (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="종료일 (YYYY-MM-DD)")


class SearchCountResponse(BaseModel):
    """검색 건수 응답"""
    total: int
    term: str
    estimated_hours: float


# =============================================================================
# ETL Schemas
# =============================================================================

class ETLStartRequest(BaseModel):
    """ETL 시작 요청"""
    term: str = Field(..., description="검색 키워드")
    limit: int = Field(100, ge=1, le=10000, description="수집할 논문 수")
    offset: int = Field(0, ge=0, description="시작 위치")


class ETLStatusResponse(BaseModel):
    """ETL 상태 응답"""
    job_id: str
    status: Literal["idle", "running", "completed", "error"]
    progress: float = Field(description="진행률 (0-100)")
    collected: int
    total: int
    message: str = ""


# =============================================================================
# Semantic Search Schemas
# =============================================================================

class SemanticSearchRequest(BaseModel):
    """의미 검색 요청"""
    query: str = Field(..., description="검색 쿼리")
    limit: int = Field(10, ge=1, le=100, description="결과 수")
    score_threshold: float = Field(0.5, ge=0.0, le=1.0, description="최소 유사도")


class SemanticSearchResult(BaseModel):
    """의미 검색 결과 항목"""
    pmid: str
    title: str
    abstract: str
    score: float
    authors: list[str]
    journal: Optional[str]
    pubdate: Optional[str]


class SemanticSearchResponse(BaseModel):
    """의미 검색 응답"""
    query: str
    results: list[SemanticSearchResult]
    total: int


# =============================================================================
# Embedding Schemas
# =============================================================================

class EmbeddingStatusResponse(BaseModel):
    """임베딩 상태 응답"""
    pending: int
    processing: int
    done: int
    error: int
    total: int
