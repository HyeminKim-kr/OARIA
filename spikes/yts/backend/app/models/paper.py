"""Paper 모델

papers, paper_authors 테이블 매핑
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Paper(Base):
    """논문 메타데이터 테이블"""

    __tablename__ = "papers"

    # 식별자
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    paper_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    pmcid: Mapped[Optional[str]] = mapped_column(String(20))
    pmid: Mapped[Optional[str]] = mapped_column(String(20))
    doi: Mapped[Optional[str]] = mapped_column(String(200))

    # 메타데이터
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    journal: Mapped[Optional[str]] = mapped_column(String(500))
    year: Mapped[Optional[int]] = mapped_column(Integer)
    keywords: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))

    # 원문 관리 (S3)
    canonical_bucket: Mapped[Optional[str]] = mapped_column(
        String(100), default="oaria-papers"
    )
    canonical_prefix: Mapped[Optional[str]] = mapped_column(Text)

    # 수집 정보
    source: Mapped[str] = mapped_column(String(50), default="europe_pmc")
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    is_open_access: Mapped[bool] = mapped_column(Boolean, default=True)

    # 처리 상태
    status: Mapped[str] = mapped_column(String(20), default="collected")

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    authors: Mapped[list["PaperAuthor"]] = relationship(
        "PaperAuthor", back_populates="paper", order_by="PaperAuthor.author_order"
    )


class PaperAuthor(Base):
    """논문 저자 테이블"""

    __tablename__ = "paper_authors"

    paper_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    author_order: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_corresponding: Mapped[bool] = mapped_column(Boolean, default=False)
    orcid: Mapped[Optional[str]] = mapped_column(String(50))
    affiliation: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    paper: Mapped["Paper"] = relationship("Paper", back_populates="authors")
