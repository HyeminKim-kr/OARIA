"""SocialAccount 모델"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class SocialAccount(Base):
    """소셜 로그인 연동 모델

    사용자의 소셜 로그인 정보 저장
    한 사용자가 여러 소셜 계정을 연동할 수 있음
    """

    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_social_accounts_provider_provider_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Provider info
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_picture: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # OAuth tokens (optional, encrypted in production)
    access_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text(), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps
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

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="social_accounts")

    def __repr__(self) -> str:
        return f"<SocialAccount {self.provider}:{self.provider_id}>"
