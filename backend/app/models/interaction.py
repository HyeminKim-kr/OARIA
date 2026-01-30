"""User Interaction 모델

paper_likes, bookmark_collections, paper_bookmarks 테이블 매핑
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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .paper import Paper
    from .user import User


class PaperLike(Base):
    """논문 좋아요 테이블 (복합 PK)"""

    __tablename__ = "paper_likes"
    __table_args__ = (
        Index("ix_paper_likes_paper_id", "paper_id"),
        Index("ix_paper_likes_user_id", "user_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    paper_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("papers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="paper_likes")
    paper: Mapped["Paper"] = relationship("Paper", back_populates="likes")


class BookmarkCollection(Base):
    """북마크 컬렉션(폴더) 테이블

    유저당 기본 컬렉션("All Bookmarks") 1개가 lazy 생성됩니다.
    partial unique index로 유저당 is_default=true 1개만 보장됩니다.
    """

    __tablename__ = "bookmark_collections"
    __table_args__ = (
        Index(
            "uq_bookmark_collections_user_default",
            "user_id",
            unique=True,
            postgresql_where="is_default = true",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="bookmark_collections")
    bookmarks: Mapped[list["PaperBookmark"]] = relationship(
        "PaperBookmark", back_populates="collection"
    )


class PaperBookmark(Base):
    """논문 북마크 테이블

    유저-논문 조합 유니크. 컬렉션에 소속 가능 (nullable).
    컬렉션 삭제 시 collection_id는 NULL로 설정 (ON DELETE SET NULL).
    서비스 레이어에서 기본 컬렉션으로 이동 처리합니다.
    """

    __tablename__ = "paper_bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "paper_id", name="uq_paper_bookmarks_user_paper"),
        Index("ix_paper_bookmarks_user_id", "user_id"),
        Index("ix_paper_bookmarks_paper_id", "paper_id"),
        Index("ix_paper_bookmarks_collection_id", "collection_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    paper_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("papers.id", ondelete="CASCADE"),
        nullable=False,
    )
    collection_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("bookmark_collections.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="paper_bookmarks")
    paper: Mapped["Paper"] = relationship("Paper", back_populates="bookmarks")
    collection: Mapped[Optional["BookmarkCollection"]] = relationship(
        "BookmarkCollection", back_populates="bookmarks"
    )
