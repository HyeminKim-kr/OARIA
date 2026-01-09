"""RAG Settings 모델

Admin에서 설정한 RAG 전략을 저장하는 테이블 (읽기 전용)
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RAGSettings(Base):
    """RAG 설정 모델

    Admin Backend에서 관리하며, User Backend는 읽기만 수행.
    is_active=True인 설정이 서버 시작 시 로드됨.
    """

    __tablename__ = "rag_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    chunker: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="semantic",
    )
    embedder: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="openai",
    )
    retriever: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="hybrid",
    )
    reranker: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    parameters: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<RAGSettings {self.name} active={self.is_active}>"
