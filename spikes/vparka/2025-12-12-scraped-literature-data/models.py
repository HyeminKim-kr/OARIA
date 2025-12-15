"""
PubMed/PMC ETL System - Pydantic 모델 정의

이 모듈은 PubMed 논문 데이터의 구조를 정의합니다.
RAG 최적화를 위한 섹션 구조와 메타데이터를 포함합니다.
"""

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class PaperMetadata(BaseModel):
    """논문 메타데이터 - PubMed ESummary에서 추출"""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    journal: str = ""
    pubdate: str = ""
    doi: str = ""
    mesh_terms: list[str] = Field(default_factory=list)


class PaperSections(BaseModel):
    """논문 섹션 구조 - PMC Full-text에서 추출 (선택적)"""
    introduction: str = ""
    methods: str = ""
    results: str = ""
    discussion: str = ""


class Paper(BaseModel):
    """
    논문 데이터 모델
    
    PubMed와 PMC에서 수집한 데이터를 통합한 구조입니다.
    - pmid: PubMed ID (필수)
    - pmcid: PMC ID (Open Access 논문만 존재)
    - metadata: 제목, 저자, 저널 등 기본 정보
    - abstract: 초록 텍스트
    - sections: Full-text 섹션 (PMC Open Access만)
    - status: 수집 상태 (ok, no_pmc, error)
    - log: 처리 로그 (디버깅용)
    """
    pmid: str
    pmcid: Optional[str] = None
    metadata: PaperMetadata = Field(default_factory=PaperMetadata)
    abstract: str = ""
    sections: Optional[PaperSections] = None
    status: Literal["ok", "no_pmc", "error"] = "ok"
    log: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    """검색 요청 모델"""
    term: str = Field(..., description="검색 키워드 (예: 'breast cancer')")
    date_from: Optional[str] = Field(None, description="시작일 (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="종료일 (YYYY-MM-DD)")
    limit: int = Field(20, ge=1, le=10000, description="가져올 최대 논문 수")
    offset: int = Field(0, ge=0, description="시작 위치")


class SearchCountResponse(BaseModel):
    """검색 건수 응답"""
    total: int
    term: str
    estimated_hours: float = Field(description="예상 소요 시간 (3 req/sec 기준)")


class SearchPreviewResponse(BaseModel):
    """검색 미리보기 응답"""
    papers: list[Paper]
    total: int
    term: str
    offset: int
    limit: int


class CrawlStartRequest(BaseModel):
    """크롤링 시작 요청"""
    term: str
    offset: int = 0
    limit: int = 1000
    batch_size: int = Field(500, ge=10, le=10000, description="배치당 논문 수")


class CrawlStatusResponse(BaseModel):
    """크롤링 상태 응답"""
    job_id: str
    status: Literal["idle", "running", "paused", "completed", "error"]
    progress: float = Field(description="진행률 (0-100)")
    collected: int
    total: int
    current_offset: int
    started_at: Optional[datetime] = None
    papers: list[Paper] = Field(default_factory=list, description="수집된 논문 (최근 배치)")
