"""Batch 모델

search_queries, batch_jobs, batch_articles, batch_errors,
batch_logs, batch_failed_items, watermarks 테이블 매핑
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SearchQuery(Base):
    """검색 쿼리 정의 테이블"""

    __tablename__ = "search_queries"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # 쿼리 타입 (production: 프로덕션, sample: 샘플/실험용)
    query_type: Mapped[str] = mapped_column(String(20), default="production")

    # 수집 설정
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=10)
    max_results: Mapped[Optional[int]] = mapped_column(Integer)
    year_from: Mapped[Optional[int]] = mapped_column(Integer)
    year_to: Mapped[Optional[int]] = mapped_column(Integer)
    open_access_only: Mapped[bool] = mapped_column(Boolean, default=True)

    # 성능 설정
    max_concurrent: Mapped[int] = mapped_column(Integer, default=35)
    auto_backfill: Mapped[bool] = mapped_column(Boolean, default=False)

    # 통계
    total_collected: Mapped[int] = mapped_column(Integer, default=0)
    last_backfill_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_incremental_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    updated_by: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    jobs: Mapped[list["BatchJob"]] = relationship(
        "BatchJob", back_populates="search_query"
    )
    sample_embeddings: Mapped[list["SampleEmbedding"]] = relationship(
        "SampleEmbedding", back_populates="search_query", cascade="all, delete-orphan"
    )


class BatchJob(Base):
    """배치 작업 큐 테이블"""

    __tablename__ = "batch_jobs"
    __table_args__ = (
        Index("idx_batch_jobs_pending", "priority", "created_at",
              postgresql_where="status IN ('pending', 'delayed')"),
        Index("idx_batch_jobs_delayed", "next_run_at",
              postgresql_where="status = 'delayed'"),
        Index("idx_batch_jobs_stale_lock", "locked_at",
              postgresql_where="status = 'running'"),
        Index("idx_batch_jobs_type", "job_type", "status"),
        Index("idx_batch_jobs_query", "query_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    query_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("search_queries.id")
    )
    priority: Mapped[int] = mapped_column(Integer, default=10)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSONB)
    api_name: Mapped[str] = mapped_column(String(50), default="europe_pmc")

    # 상태 관리
    status: Mapped[str] = mapped_column(String(20), default="pending")
    checkpoint: Mapped[Optional[dict]] = mapped_column(JSONB)

    # 진행률
    total_count: Mapped[Optional[int]] = mapped_column(Integer)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)

    # 재시도 관리
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 워커 락
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[Optional[str]] = mapped_column(String(100))

    # 에러 추적
    last_error_code: Mapped[Optional[str]] = mapped_column(String(20))
    last_error_message: Mapped[Optional[str]] = mapped_column(Text)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationships
    search_query: Mapped[Optional["SearchQuery"]] = relationship(
        "SearchQuery", back_populates="jobs"
    )
    articles: Mapped[list["BatchArticle"]] = relationship(
        "BatchArticle", back_populates="job", cascade="all, delete-orphan"
    )
    errors: Mapped[list["BatchError"]] = relationship(
        "BatchError", back_populates="job", cascade="all, delete-orphan"
    )
    logs: Mapped[list["BatchLog"]] = relationship(
        "BatchLog", back_populates="job", cascade="all, delete-orphan"
    )
    failed_items: Mapped[list["BatchFailedItem"]] = relationship(
        "BatchFailedItem", back_populates="job"
    )


class BatchArticle(Base):
    """개별 논문 수집 상태 테이블"""

    __tablename__ = "batch_articles"
    __table_args__ = (
        UniqueConstraint("job_id", "pmcid", name="uq_batch_articles_job_pmcid"),
        Index("idx_batch_articles_status", "job_id", "status"),
        Index("idx_batch_articles_retry", "status", "next_run_at",
              postgresql_where="status IN ('pending', 'failed')"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("batch_jobs.id", ondelete="CASCADE"),
        nullable=False
    )
    pmcid: Mapped[str] = mapped_column(String(20), nullable=False)
    pmid: Mapped[Optional[str]] = mapped_column(String(20))
    doi: Mapped[Optional[str]] = mapped_column(String(100))
    article_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)

    # 상태
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # 재시도
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 에러
    last_error_code: Mapped[Optional[str]] = mapped_column(String(20))
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    job: Mapped["BatchJob"] = relationship(
        "BatchJob", back_populates="articles"
    )


class BatchError(Base):
    """배치 에러 로그 테이블"""

    __tablename__ = "batch_errors"
    __table_args__ = (
        Index("idx_batch_errors_job", "job_id", "created_at"),
        Index("idx_batch_errors_pmcid", "pmcid"),
        Index("idx_batch_errors_stage", "stage"),
        Index("idx_batch_errors_code", "error_code"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    job_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("batch_jobs.id", ondelete="CASCADE")
    )
    pmcid: Mapped[Optional[str]] = mapped_column(String(20))
    pmid: Mapped[Optional[str]] = mapped_column(String(20))
    doi: Mapped[Optional[str]] = mapped_column(String(100))

    # 에러 정보
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(50))
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    error_detail: Mapped[Optional[str]] = mapped_column(Text)

    # 컨텍스트
    raw_response: Mapped[Optional[str]] = mapped_column(Text)
    context: Mapped[Optional[dict]] = mapped_column(JSONB)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    job: Mapped[Optional["BatchJob"]] = relationship(
        "BatchJob", back_populates="errors"
    )


class BatchLog(Base):
    """배치 실행 로그 테이블"""

    __tablename__ = "batch_logs"
    __table_args__ = (
        Index("idx_batch_logs_job", "job_id", "created_at"),
        Index("idx_batch_logs_level", "level", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    job_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("batch_jobs.id", ondelete="CASCADE")
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    job: Mapped[Optional["BatchJob"]] = relationship(
        "BatchJob", back_populates="logs"
    )


class BatchFailedItem(Base):
    """실패 항목 추적 테이블"""

    __tablename__ = "batch_failed_items"
    __table_args__ = (
        Index("idx_failed_items_status", "status", "next_retry_at"),
        Index("idx_failed_items_job", "job_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    job_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("batch_jobs.id")
    )
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[Optional[str]] = mapped_column(String(100))

    # 에러 정보
    error_code: Mapped[Optional[str]] = mapped_column(String(20))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # 재시도
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 상태
    status: Mapped[str] = mapped_column(String(20), default="pending")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    job: Mapped[Optional["BatchJob"]] = relationship(
        "BatchJob", back_populates="failed_items"
    )


class Watermark(Base):
    """증분 수집 상태 테이블"""

    __tablename__ = "watermarks"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    overlap_days: Mapped[int] = mapped_column(Integer, default=2)
    last_query: Mapped[Optional[str]] = mapped_column(Text)
    last_result_count: Mapped[Optional[int]] = mapped_column(Integer)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )


class SampleEmbedding(Base):
    """샘플 임베딩 테이블

    샘플 쿼리로 수집된 논문들을 다양한 청킹/임베딩 전략으로
    임베딩한 결과를 관리합니다.
    """

    __tablename__ = "sample_embeddings"
    __table_args__ = (
        UniqueConstraint("query_id", "pipeline_key", name="uq_sample_embeddings_query_pipeline"),
        Index("idx_sample_embeddings_query_id", "query_id"),
        Index("idx_sample_embeddings_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )

    # 샘플 쿼리 참조
    query_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("search_queries.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 파이프라인 정보
    chunker: Mapped[str] = mapped_column(String(100), nullable=False)
    embedder: Mapped[str] = mapped_column(String(100), nullable=False)
    pipeline_key: Mapped[str] = mapped_column(String(200), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 상태
    status: Mapped[str] = mapped_column(String(20), default="pending")
    paper_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    search_query: Mapped["SearchQuery"] = relationship(
        "SearchQuery", back_populates="sample_embeddings"
    )
