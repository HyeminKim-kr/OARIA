"""Paper 모델

papers, paper_authors, paper_sections, paper_relations, paper_citations 테이블 매핑
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .chat import Conversation
    from .interaction import PaperLike, PaperBookmark


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
    year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    keywords: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))

    # 원문 관리 (S3)
    canonical_bucket: Mapped[Optional[str]] = mapped_column(
        String(100), default="oaria-papers"
    )
    canonical_prefix: Mapped[Optional[str]] = mapped_column(Text)
    canonical_text_version: Mapped[Optional[str]] = mapped_column(
        String(50), default="v1"
    )
    canonical_text_hash: Mapped[Optional[str]] = mapped_column(String(64))
    canonical_text_length: Mapped[Optional[int]] = mapped_column(Integer)

    # 변경 추적
    raw_xml_hash: Mapped[Optional[str]] = mapped_column(String(64))
    parser_version: Mapped[Optional[str]] = mapped_column(String(20), default="1.0.0")

    # 수집 정보
    source: Mapped[str] = mapped_column(String(50), default="europe_pmc")
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    is_open_access: Mapped[bool] = mapped_column(Boolean, default=True)

    # 처리 상태
    status: Mapped[str] = mapped_column(String(20), default="collected", index=True)
    chunked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 임베딩 상태
    embedding_status: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    embedding_chunk_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    embedding_error: Mapped[Optional[str]] = mapped_column(Text)
    embedding_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 논문 유형 및 관계 플래그
    pub_types: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    has_correction: Mapped[bool] = mapped_column(Boolean, default=False)
    has_erratum: Mapped[bool] = mapped_column(Boolean, default=False)
    has_retraction: Mapped[bool] = mapped_column(Boolean, default=False)

    # PDF 관련
    has_pdf: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    pdf_size: Mapped[Optional[int]] = mapped_column(Integer)
    pdf_hash: Mapped[Optional[str]] = mapped_column(String(64))
    pdf_downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 인용 통계
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    reference_count: Mapped[int] = mapped_column(Integer, default=0)

    # 좋아요 캐시
    like_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()", index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    authors: Mapped[list["PaperAuthor"]] = relationship(
        "PaperAuthor", back_populates="paper", order_by="PaperAuthor.author_order",
        cascade="all, delete-orphan"
    )
    sections: Mapped[list["PaperSection"]] = relationship(
        "PaperSection", back_populates="paper", order_by="PaperSection.section_order",
        cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="paper"
    )
    summaries: Mapped[list["PaperSummary"]] = relationship(
        "PaperSummary", back_populates="paper", cascade="all, delete-orphan"
    )
    likes: Mapped[list["PaperLike"]] = relationship(
        "PaperLike", back_populates="paper", cascade="all, delete-orphan"
    )
    bookmarks: Mapped[list["PaperBookmark"]] = relationship(
        "PaperBookmark", back_populates="paper", cascade="all, delete-orphan"
    )


class PaperAuthor(Base):
    """논문 저자 테이블"""

    __tablename__ = "paper_authors"

    paper_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    author_order: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    author_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    is_corresponding: Mapped[bool] = mapped_column(Boolean, default=False)
    orcid: Mapped[Optional[str]] = mapped_column(String(50))
    affiliation: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    paper: Mapped["Paper"] = relationship("Paper", back_populates="authors")


class PaperSection(Base):
    """논문 섹션 오프셋 정보 테이블"""

    __tablename__ = "paper_sections"
    __table_args__ = (
        UniqueConstraint("paper_id", "section_order", name="uq_paper_sections_order"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    paper_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    section_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    section_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    section_title: Mapped[Optional[str]] = mapped_column(Text)
    offset_start: Mapped[int] = mapped_column(Integer, nullable=False)
    offset_end: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    paper: Mapped["Paper"] = relationship("Paper", back_populates="sections")


class PaperRelation(Base):
    """논문 간 관계 테이블 (정정/철회/코멘트)"""

    __tablename__ = "paper_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_pmid", "target_pmid", "relation_type",
            name="uq_paper_relations"
        ),
        Index("idx_paper_relations_target", "target_pmid"),
        Index("idx_paper_relations_source", "source_pmid"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    source_pmid: Mapped[str] = mapped_column(Text, nullable=False)
    target_pmid: Mapped[str] = mapped_column(Text, nullable=False)
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    raw_type: Mapped[Optional[str]] = mapped_column(Text)
    reference: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )


class PaperCitation(Base):
    """논문 인용 관계 테이블 (Citations/References)"""

    __tablename__ = "paper_citations"
    __table_args__ = (
        UniqueConstraint(
            "source_paper_id", "target_paper_id",
            name="uq_paper_citations"
        ),
        Index("idx_paper_citations_source", "source_paper_id"),
        Index("idx_paper_citations_target", "target_paper_id"),
        Index("idx_paper_citations_collected", "collected_from"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    # 인용하는 논문 (citing paper)
    source_paper_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # 인용되는 논문 (cited paper)
    target_paper_id: Mapped[str] = mapped_column(String(100), nullable=False)
    # 추가 식별자
    source_pmcid: Mapped[Optional[str]] = mapped_column(String(20))
    source_pmid: Mapped[Optional[str]] = mapped_column(String(20))
    target_pmcid: Mapped[Optional[str]] = mapped_column(String(20))
    target_pmid: Mapped[Optional[str]] = mapped_column(String(20))
    # 어떤 논문 수집 시 발견됨
    collected_from: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )


class PaperSummary(Base):
    """논문 요약 캐시 테이블

    LLM이 생성한 논문 요약을 캐싱하여 중복 생성을 방지합니다.
    임베딩은 백그라운드에서 처리되어 기존 PaperChunk 컬렉션에 저장됩니다.
    """

    __tablename__ = "paper_summaries"
    __table_args__ = (
        UniqueConstraint("paper_id", "summary_type", name="uq_paper_summary"),
        Index("idx_paper_summaries_paper_id", "paper_id"),
        Index("idx_paper_summaries_embedding_status", "embedding_status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    paper_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    summary_type: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    sections_used: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)

    # 임베딩 상태
    embedding_status: Mapped[Optional[str]] = mapped_column(String(20), default="pending")
    embedding_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    paper: Mapped["Paper"] = relationship("Paper", back_populates="summaries")
