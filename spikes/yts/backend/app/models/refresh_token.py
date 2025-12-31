"""RefreshToken 모델"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class UserRefreshToken(Base):
    """사용자 JWT Refresh Token 모델

    JWT refresh token을 DB에서 관리하여
    token rotation, revocation을 지원
    """

    __tablename__ = "user_refresh_tokens"

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

    # Token info (store hash, not actual token)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Device tracking
    device_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 support

    # Revocation
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    @property
    def is_valid(self) -> bool:
        """토큰이 유효한지 확인"""
        if self.revoked_at is not None:
            return False
        if self.expires_at < datetime.now(self.expires_at.tzinfo):
            return False
        return True

    def revoke(self, reason: str = "logout") -> None:
        """토큰 폐기"""
        self.revoked_at = datetime.now(self.expires_at.tzinfo)
        self.revoked_reason = reason

    def __repr__(self) -> str:
        status = "valid" if self.is_valid else "invalid"
        return f"<UserRefreshToken {self.id} ({status})>"
