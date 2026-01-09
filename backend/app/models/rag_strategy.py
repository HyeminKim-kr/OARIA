"""RAG Strategy 모델

사용 가능한 RAG 전략 목록을 저장하는 테이블.
서버 시작 시 코드에서 자동 동기화됨.
"""

import uuid
from datetime import datetime
from typing import Any, Optional, Dict

from sqlalchemy import Boolean, DateTime, String, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RAGStrategy(Base):
    """RAG 전략 모델

    코드에 정의된 전략 정보를 DB에 저장.
    서버 시작 시 자동으로 동기화됨.
    """

    __tablename__ = "rag_strategies"
    __table_args__ = (
        UniqueConstraint("category", "name", name="uq_rag_strategies_category_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="전략 카테고리 (chunker, embedder, retriever, reranker)",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="전략 이름",
    )
    description: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        comment="전략 설명 (docstring에서 추출)",
    )
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="기본 설정값",
    )
    location: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="실행 위치 (backend or batch)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="활성 여부",
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
        return f"<RAGStrategy {self.category}/{self.name} location={self.location}>"
