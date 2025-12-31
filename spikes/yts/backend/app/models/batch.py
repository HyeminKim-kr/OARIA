"""Batch 모델

search_queries, collection_jobs, article_jobs, article_errors,
batch_job_logs, batch_failed_items, watermarks 테이블 매핑
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
    jobs: Mapped[list["CollectionJob"]] = relationship(
        "CollectionJob", back_populates="search_query"
    )


class CollectionJob(Base):
    """배치 작업 큐 테이블"""

    __tablename__ = "collection_jobs"
    __table_args__ = (
        Index("idx_jobs_pending", "priority", "created_at",
              postgresql_where="status IN ('pending', 'delayed')"),
        Index("idx_jobs_delayed", "next_run_at",
              postgresql_where="status = 'delayed'"),
        Index("idx_jobs_stale_lock", "locked_at",
              postgresql_where="status = 'running'"),
        Index("idx_jobs_type", "job_type", "status"),
        Index("idx_jobs_query", "query_id", "created_at"),
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
    article_jobs: Mapped[list["ArticleJob"]] = relationship(
        "ArticleJob", back_populates="batch_job", cascade="all, delete-orphan"
    )
    article_errors: Mapped[list["ArticleError"]] = relationship(
        "ArticleError", back_populates="job", cascade="all, delete-orphan"
    )
    logs: Mapped[list["BatchJobLog"]] = relationship(
        "BatchJobLog", back_populates="job", cascade="all, delete-orphan"
    )
    failed_items: Mapped[list["BatchFailedItem"]] = relationship(
        "BatchFailedItem", back_populates="job"
    )


class ArticleJob(Base):
    """개별 논문 수집 상태 테이블"""

    __tablename__ = "article_jobs"
    __table_args__ = (
        UniqueConstraint("batch_job_id", "pmcid", name="uq_article_jobs_batch_pmcid"),
        Index("idx_article_jobs_status", "batch_job_id", "status"),
        Index("idx_article_jobs_retry", "status", "next_run_at",
              postgresql_where="status IN ('pending', 'failed')"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    batch_job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("collection_jobs.id", ondelete="CASCADE"),
        nullable=False
    )
    pmcid: Mapped[str] = mapped_column(String(20), nullable=False)
    pmid: Mapped[Optional[str]] = mapped_column(String(20))
    doi: Mapped[Optional[str]] = mapped_column(String(100))
    job_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)

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
    batch_job: Mapped["CollectionJob"] = relationship(
        "CollectionJob", back_populates="article_jobs"
    )


class ArticleError(Base):
    """아티클 에러 로그 테이블"""

    __tablename__ = "article_errors"
    __table_args__ = (
        Index("idx_article_errors_job", "job_id", "created_at"),
        Index("idx_article_errors_pmcid", "pmcid"),
        Index("idx_article_errors_stage", "stage"),
        Index("idx_article_errors_code", "error_code"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    job_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("collection_jobs.id", ondelete="CASCADE")
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
    job: Mapped[Optional["CollectionJob"]] = relationship(
        "CollectionJob", back_populates="article_errors"
    )


class BatchJobLog(Base):
    """배치 실행 로그 테이블"""

    __tablename__ = "batch_job_logs"
    __table_args__ = (
        Index("idx_job_logs_job", "job_id", "created_at"),
        Index("idx_job_logs_level", "level", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    job_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("collection_jobs.id", ondelete="CASCADE")
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    job: Mapped[Optional["CollectionJob"]] = relationship(
        "CollectionJob", back_populates="logs"
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
        PGUUID(as_uuid=True), ForeignKey("collection_jobs.id")
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
    job: Mapped[Optional["CollectionJob"]] = relationship(
        "CollectionJob", back_populates="failed_items"
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
